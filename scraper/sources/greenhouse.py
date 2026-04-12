"""Greenhouse API poller for intern job postings."""

from __future__ import annotations

import re

import httpx

from config import GREENHOUSE_COMPANIES, INTERN_TITLE_PATTERNS

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"


def is_intern_posting(title: str) -> bool:
    """Check if title matches any intern pattern."""
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in INTERN_TITLE_PATTERNS)


def parse_greenhouse_jobs(
    company_slug: str, company_name: str, raw: dict
) -> list[dict]:
    """Parse Greenhouse API response into normalized posting dicts.

    Only includes postings where the title matches intern patterns.
    """
    jobs = raw.get("jobs", [])
    results: list[dict] = []

    for job in jobs:
        title = job.get("title", "")
        if not is_intern_posting(title):
            continue

        departments = job.get("departments", [])
        team = departments[0].get("name", "") if departments else ""

        content = job.get("content", "")
        skills = content[:200].strip() if content else ""

        location_obj = job.get("location", {})
        location = location_obj.get("name", "") if location_obj else ""

        results.append({
            "posting_id": str(job.get("id", "")),
            "title": title,
            "url": job.get("absolute_url", ""),
            "company_slug": company_slug,
            "company_name": company_name,
            "team": team,
            "skills": skills,
            "location": location,
        })

    return results


async def fetch_jobs(slug: str, name: str) -> list[dict]:
    """Fetch and parse jobs from Greenhouse for one company."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(GREENHOUSE_API.format(slug=slug))
        resp.raise_for_status()
        return parse_greenhouse_jobs(slug, name, resp.json())


async def poll_all() -> list[dict]:
    """Fetch from all Greenhouse companies. Return combined list."""
    results: list[dict] = []
    for company in GREENHOUSE_COMPANIES:
        try:
            jobs = await fetch_jobs(company["slug"], company["name"])
            results.extend(jobs)
        except Exception:
            pass  # Log in production, skip failed companies
    return results
