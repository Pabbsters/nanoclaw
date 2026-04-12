"""Amazon Jobs JSON API poller for intern postings."""

from __future__ import annotations

import httpx

AMAZON_SEARCH_URL = "https://www.amazon.jobs/en/search.json"
AMAZON_BASE = "https://www.amazon.jobs"

DEFAULT_PARAMS: dict[str, str] = {
    "category[]": "software-development",
    "schedule_type_id[]": "intern",
    "result_limit": "25",
}


def parse_amazon_jobs(raw: dict) -> list[dict]:
    """Parse Amazon Jobs search JSON into normalized posting dicts."""
    jobs = raw.get("jobs", [])
    results: list[dict] = []

    for job in jobs:
        job_id = str(job.get("id_icims", ""))
        title = job.get("title", "")
        job_path = job.get("job_path", "")
        url = f"{AMAZON_BASE}{job_path}" if job_path else ""
        location = job.get("normalized_location", "")

        basic_quals = job.get("basic_qualifications", "") or ""
        skills = basic_quals[:200].strip()

        results.append({
            "posting_id": job_id,
            "title": title,
            "url": url,
            "company_slug": "amazon",
            "company_name": "Amazon",
            "team": "",
            "skills": skills,
            "location": location,
        })

    return results


async def fetch_jobs() -> list[dict]:
    """Fetch intern postings from Amazon Jobs API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(AMAZON_SEARCH_URL, params=DEFAULT_PARAMS)
        resp.raise_for_status()
        return parse_amazon_jobs(resp.json())


async def poll_all() -> list[dict]:
    """Fetch Amazon intern postings."""
    try:
        return await fetch_jobs()
    except Exception:
        return []
