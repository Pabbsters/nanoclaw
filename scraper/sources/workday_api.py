"""Workday internal CXS API poller — uses POST with CSRF session flow.

Some Workday-hosted career sites block the public HTML page (Cloudflare) but
still respond to the internal JSON API used by their own SPA. This module
implements the two-step approach:
  1. GET the careers page to obtain a session cookie (PLAY_SESSION / WD CSRF).
  2. POST to /wday/cxs/<tenant>/<site>/jobs with the session token.

This is distinct from sources/workday.py which scrapes JSON-LD from HTML.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from config import ALERT_TITLE_PATTERNS

logger = logging.getLogger(__name__)

# Companies that need the CXS POST approach rather than HTML/JSON-LD scraping.
# host: the Workday hostname (tenant.wdN.myworkdayjobs.com)
# site: the site slug used in the CXS path
# tenant: the tenant slug used in the CXS path (usually same as host prefix)
WORKDAY_API_COMPANIES: list[dict[str, str]] = [
    {
        "slug": "tesla",
        "name": "Tesla",
        "host": "tesla.wd1.myworkdayjobs.com",
        "tenant": "tesla",
        "site": "teslamotors",
    },
]

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def is_intern_posting(title: str) -> bool:
    """Check if title matches any intern pattern."""
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in ALERT_TITLE_PATTERNS)


def _extract_csrf(headers: httpx.Headers, html: str) -> str | None:
    """Extract CSRF token from Set-Cookie header or page HTML."""
    # Workday sets PLAY_SESSION which doubles as the CSRF token value in some tenants
    set_cookie = headers.get("set-cookie", "")
    m = re.search(r"PLAY_SESSION=([^;]+)", set_cookie)
    if m:
        return m.group(1)
    # Fallback: look for token in page HTML
    m = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', html)
    if m:
        return m.group(1)
    return None


def parse_workday_api_jobs(
    company_slug: str, company_name: str, host: str, raw: dict[str, Any]
) -> list[dict]:
    """Parse Workday CXS API JSON response into normalized posting dicts."""
    job_postings = raw.get("jobPostings", [])
    results: list[dict] = []

    for job in job_postings:
        title = job.get("title", "")
        if not is_intern_posting(title):
            continue

        external_path = job.get("externalPath", "")
        url = f"https://{host}{external_path}" if external_path else ""

        posted_on = job.get("postedOn", "")
        # Workday returns "Posted 3 Days Ago" style text — extract date if ISO
        posted_at = posted_on if re.match(r"\d{4}-\d{2}-\d{2}", posted_on) else ""

        location_obj = job.get("locationsText", "") or job.get("jobLocations", "")
        if isinstance(location_obj, list):
            location = ", ".join(str(l) for l in location_obj[:2])
        else:
            location = str(location_obj).strip()

        results.append({
            "posting_id": str(job.get("bulletFields", [""])[0] or job.get("externalPath", "")).strip("/"),
            "title": title,
            "url": url,
            "company_slug": company_slug,
            "company_name": company_name,
            "team": "",
            "skills": "",
            "location": location,
            "posted_at": posted_at,
        })

    return results


async def fetch_jobs(
    slug: str, name: str, host: str, tenant: str, site: str
) -> list[dict]:
    """Two-step Workday CXS fetch: get session then POST jobs search."""
    careers_url = f"https://{host}/en-US/{site}"
    api_url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"

    headers = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}

    async with httpx.AsyncClient(
        timeout=45,
        follow_redirects=True,
        headers={"User-Agent": _UA},
    ) as client:
        # Step 1: hit the careers page to get cookies
        try:
            get_resp = await client.get(careers_url, headers=headers)
            csrf = _extract_csrf(get_resp.headers, get_resp.text)
        except Exception:
            csrf = None

        # Step 2: POST to the jobs API
        post_headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _UA,
            "Referer": careers_url,
        }
        if csrf:
            post_headers["X-CSRF-Token"] = csrf

        payload = {
            "appliedFacets": {},
            "limit": 20,
            "offset": 0,
            "searchText": "intern",
        }

        resp = await client.post(api_url, json=payload, headers=post_headers)
        resp.raise_for_status()
        return parse_workday_api_jobs(slug, name, host, resp.json())


async def poll_all() -> list[dict]:
    """Fetch from all Workday API companies. Return combined list."""
    results: list[dict] = []
    for company in WORKDAY_API_COMPANIES:
        try:
            jobs = await fetch_jobs(
                slug=company["slug"],
                name=company["name"],
                host=company["host"],
                tenant=company["tenant"],
                site=company["site"],
            )
            results.extend(jobs)
        except Exception as exc:
            logger.debug("Workday API fetch failed for %s: %s", company["slug"], exc)
    return results
