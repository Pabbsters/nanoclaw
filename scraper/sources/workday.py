"""Best-effort Workday and consulting career page scraper.

Workday APIs are undocumented and fragile. This module fetches career page
HTML and looks for JSON-LD ``JobPosting`` structured data or falls back to
link-based heuristics.  Everything is wrapped in broad exception handlers
so failures never break the main polling loop.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from config import ALERT_TITLE_PATTERNS

logger = logging.getLogger(__name__)

WORKDAY_COMPANIES: list[dict[str, str]] = [
    {"slug": "nvidia", "host": "nvidia.wd5.myworkdayjobs.com", "path": "/en-US/NVIDIAExternalCareerSite", "name": "Nvidia"},
    {"slug": "adobe", "host": "adobe.wd5.myworkdayjobs.com", "path": "/en-US/external_experienced", "name": "Adobe"},
    {"slug": "salesforce", "host": "salesforce.wd12.myworkdayjobs.com", "path": "/en-US/External_Career_Site", "name": "Salesforce"},
]

# Regex to extract JSON-LD blocks from HTML
_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def is_intern_posting(title: str) -> bool:
    """Check if title matches any intern pattern."""
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in ALERT_TITLE_PATTERNS)


def _extract_jsonld_postings(html: str) -> list[dict[str, Any]]:
    """Extract JobPosting objects from JSON-LD script tags."""
    postings: list[dict[str, Any]] = []
    for match in _JSONLD_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            continue

        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]

        for item in items:
            if item.get("@type") == "JobPosting":
                postings.append(item)

    return postings


def parse_jsonld_jobs(
    company_slug: str, company_name: str, html: str
) -> list[dict]:
    """Parse JSON-LD JobPosting data from HTML into normalized posting dicts.

    Only includes postings where the title matches intern patterns.
    """
    jsonld_items = _extract_jsonld_postings(html)
    results: list[dict] = []

    for item in jsonld_items:
        title = item.get("title", "") or item.get("name", "")
        if not title or not is_intern_posting(title):
            continue

        url = item.get("url", "")
        description = item.get("description", "")
        skills = description[:200].strip() if description else ""

        identifier = item.get("identifier", {})
        posting_id = ""
        if isinstance(identifier, dict):
            posting_id = str(identifier.get("value", ""))
        if not posting_id:
            posting_id = str(hash(f"{company_slug}:{title}:{url}"))

        location = ""
        job_location = item.get("jobLocation", {})
        if isinstance(job_location, dict):
            address = job_location.get("address", {})
            if isinstance(address, dict):
                location = address.get("addressLocality", "")
        posted_at = str(item.get("datePosted", "")).strip()

        results.append({
            "posting_id": posting_id,
            "title": title,
            "url": url,
            "company_slug": company_slug,
            "company_name": company_name,
            "team": "",
            "skills": skills,
            "location": location,
            "posted_at": posted_at,
        })

    return results


async def fetch_company_page(
    host: str, path: str, slug: str, name: str
) -> list[dict]:
    """Fetch a career page and extract intern postings (best-effort)."""
    url = f"https://{host}{path}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; jojo-scraper/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return parse_jsonld_jobs(slug, name, resp.text)


async def poll_all() -> list[dict]:
    """Best-effort scrape of Workday and consulting career pages."""
    results: list[dict] = []
    for company in WORKDAY_COMPANIES:
        try:
            jobs = await fetch_company_page(
                host=company["host"],
                path=company["path"],
                slug=company["slug"],
                name=company["name"],
            )
            results.extend(jobs)
        except Exception as exc:
            logger.debug("Workday fetch failed for %s: %s", company["slug"], exc)
    return results
