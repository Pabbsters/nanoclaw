"""SmartRecruiters API poller for intern job postings."""

from __future__ import annotations

import re

import httpx

from config import ALERT_TITLE_PATTERNS

SMARTRECRUITERS_API = "https://api.smartrecruiters.com/v1/companies/{company_id}/postings"

SMARTRECRUITERS_COMPANIES: list[dict[str, str]] = [
    {"slug": "snap", "company_id": "SnapInc", "name": "Snap"},
    {"slug": "spotify", "company_id": "SpotifyAB", "name": "Spotify"},
    {"slug": "grammarly", "company_id": "Grammarly", "name": "Grammarly"},
    {"slug": "millennium", "company_id": "MillenniumManagement", "name": "Millennium"},
    {"slug": "uber", "company_id": "Uber", "name": "Uber"},
    {"slug": "doordash", "company_id": "DoorDash", "name": "DoorDash"},
]


def is_intern_posting(title: str) -> bool:
    """Check if title matches any intern pattern."""
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in ALERT_TITLE_PATTERNS)


def parse_smartrecruiters_jobs(
    company_slug: str, company_name: str, raw: dict
) -> list[dict]:
    """Parse SmartRecruiters API response into normalized posting dicts.

    Only includes postings where the title matches intern patterns.
    """
    content = raw.get("content", [])
    results: list[dict] = []

    for job in content:
        title = job.get("name", "")
        if not is_intern_posting(title):
            continue

        dept = job.get("department", {})
        team = dept.get("label", "") if isinstance(dept, dict) else ""

        location_obj = job.get("location", {})
        if isinstance(location_obj, dict):
            city = location_obj.get("city", "")
            country = location_obj.get("country", "")
            remote = location_obj.get("remote", False)
            if remote:
                location = "Remote"
            elif city and country:
                location = f"{city}, {country.upper()}"
            else:
                location = city or country or ""
        else:
            location = ""

        released = job.get("releasedDate", "") or job.get("updatedDate", "")
        posted_at = released[:10] if released else ""

        results.append({
            "posting_id": str(job.get("id", "")),
            "title": title,
            "url": job.get("ref", ""),
            "company_slug": company_slug,
            "company_name": company_name,
            "team": team,
            "skills": "",
            "location": location,
            "posted_at": posted_at,
        })

    return results


async def fetch_jobs(company_slug: str, company_id: str, name: str) -> list[dict]:
    """Fetch and parse jobs from SmartRecruiters for one company."""
    url = SMARTRECRUITERS_API.format(company_id=company_id)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params={"limit": 100})
        resp.raise_for_status()
        return parse_smartrecruiters_jobs(company_slug, name, resp.json())


async def poll_all() -> list[dict]:
    """Fetch from all SmartRecruiters companies. Return combined list."""
    results: list[dict] = []
    for company in SMARTRECRUITERS_COMPANIES:
        try:
            jobs = await fetch_jobs(
                company["slug"],
                company["company_id"],
                company["name"],
            )
            results.extend(jobs)
        except Exception:
            pass  # Log in production, skip failed companies
    return results
