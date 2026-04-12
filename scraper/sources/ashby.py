"""Ashby API poller for intern job postings."""

from __future__ import annotations

import re

import httpx

from config import ASHBY_COMPANIES, INTERN_TITLE_PATTERNS

ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def is_intern_posting(title: str) -> bool:
    """Check if title matches any intern pattern."""
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in INTERN_TITLE_PATTERNS)


def parse_ashby_jobs(
    company_slug: str, company_name: str, raw: dict | list
) -> list[dict]:
    """Parse Ashby API response into normalized posting dicts.

    Ashby responses may have jobs under a ``jobs`` key or as a root array.
    Only includes postings where the title matches intern patterns.
    """
    if isinstance(raw, dict):
        jobs = raw.get("jobs", [])
    else:
        jobs = raw

    results: list[dict] = []

    for job in jobs:
        title = job.get("title", "")
        if not is_intern_posting(title):
            continue

        team = job.get("departmentName", "") or job.get("team", "")
        location = job.get("location", "")
        if isinstance(location, dict):
            location = location.get("name", "")

        description = job.get("descriptionPlain", "") or job.get("description", "")
        skills = description[:200].strip() if description else ""

        posting_url = job.get("hostedUrl", "") or job.get("jobUrl", "")

        results.append({
            "posting_id": str(job.get("id", "")),
            "title": title,
            "url": posting_url,
            "company_slug": company_slug,
            "company_name": company_name,
            "team": team,
            "skills": skills,
            "location": location if isinstance(location, str) else "",
        })

    return results


async def fetch_jobs(slug: str, name: str) -> list[dict]:
    """Fetch and parse jobs from Ashby for one company."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(ASHBY_API.format(slug=slug))
        resp.raise_for_status()
        return parse_ashby_jobs(slug, name, resp.json())


async def poll_all() -> list[dict]:
    """Fetch from all Ashby companies. Return combined list."""
    results: list[dict] = []
    for company in ASHBY_COMPANIES:
        try:
            jobs = await fetch_jobs(company["slug"], company["name"])
            results.extend(jobs)
        except Exception:
            pass  # Log in production, skip failed companies
    return results
