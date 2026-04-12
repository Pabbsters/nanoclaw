"""Lever API poller for intern job postings."""

from __future__ import annotations

import re

import httpx

from config import INTERN_TITLE_PATTERNS, LEVER_COMPANIES

LEVER_API = "https://api.lever.co/v0/postings/{slug}?mode=json"


def is_intern_posting(title: str) -> bool:
    """Check if title matches any intern pattern."""
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in INTERN_TITLE_PATTERNS)


def parse_lever_jobs(
    company_slug: str, company_name: str, raw: list
) -> list[dict]:
    """Parse Lever API response into normalized posting dicts.

    Lever returns a JSON array of posting objects.
    Only includes postings where the title matches intern patterns.
    """
    results: list[dict] = []

    for job in raw:
        title = job.get("text", "")
        if not is_intern_posting(title):
            continue

        categories = job.get("categories", {})
        team = categories.get("team", "") or categories.get("department", "")

        description = job.get("descriptionPlain", "")
        skills = description[:200].strip() if description else ""

        location = categories.get("location", "")

        results.append({
            "posting_id": str(job.get("id", "")),
            "title": title,
            "url": job.get("hostedUrl", ""),
            "company_slug": company_slug,
            "company_name": company_name,
            "team": team,
            "skills": skills,
            "location": location,
        })

    return results


async def fetch_jobs(slug: str, name: str) -> list[dict]:
    """Fetch and parse jobs from Lever for one company."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(LEVER_API.format(slug=slug))
        resp.raise_for_status()
        return parse_lever_jobs(slug, name, resp.json())


async def poll_all() -> list[dict]:
    """Fetch from all Lever companies. Return combined list."""
    results: list[dict] = []
    for company in LEVER_COMPANIES:
        try:
            jobs = await fetch_jobs(company["slug"], company["name"])
            results.extend(jobs)
        except Exception:
            pass  # Log in production, skip failed companies
    return results
