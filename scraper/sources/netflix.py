"""Netflix custom jobs API poller."""

from __future__ import annotations

import re
from datetime import UTC, datetime

import httpx

from config import ALERT_TITLE_PATTERNS

NETFLIX_JOBS_API = "https://explore.jobs.netflix.net/api/apply/v2/jobs"
NETFLIX_PARAMS: dict[str, object] = {
    "domain": "netflix.com",
    "query": "intern",
    "limit": 100,
    "start": 0,
}


def is_intern_posting(title: str) -> bool:
    """Check if title matches any intern pattern."""
    title_lower = title.lower()
    return any(re.search(p, title_lower) for p in ALERT_TITLE_PATTERNS)


def _format_timestamp(raw: object) -> str:
    if raw in (None, ""):
        return ""
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(raw).strip()
    if value > 10_000_000_000:
        value /= 1000
    return datetime.fromtimestamp(value, tz=UTC).isoformat().replace("+00:00", "Z")


def parse_netflix_jobs(raw: dict) -> list[dict]:
    """Parse Netflix API response into normalized posting dicts.

    Netflix returns positions under a ``positions`` key (or ``jobs`` fallback).
    Only includes postings where the title matches intern patterns.
    """
    positions = raw.get("positions", [])
    if not positions and "jobs" in raw:
        positions = raw["jobs"]

    results: list[dict] = []
    for job in positions:
        title = job.get("text", "") or job.get("title", "") or job.get("name", "")
        if not is_intern_posting(title):
            continue

        location_obj = job.get("location", {})
        if isinstance(location_obj, dict):
            location = location_obj.get("name", "") or location_obj.get("text", "")
        elif isinstance(location_obj, str):
            location = location_obj
        else:
            location = ""

        team_obj = job.get("team", {})
        if isinstance(team_obj, dict):
            team = team_obj.get("name", "")
        elif isinstance(team_obj, str):
            team = team_obj
        else:
            team = ""

        job_id = str(job.get("id", "") or job.get("externalId", ""))
        job_url = (
            job.get("externalUrl", "")
            or job.get("applyUrl", "")
            or (f"https://jobs.netflix.com/jobs/{job_id}" if job_id else "")
        )
        posted_at = _format_timestamp(job.get("created") or job.get("updatedAt"))

        results.append({
            "posting_id": job_id,
            "title": title,
            "url": job_url,
            "company_slug": "netflix",
            "company_name": "Netflix",
            "team": team,
            "skills": "",
            "location": location,
            "posted_at": posted_at,
        })

    return results


async def fetch_jobs() -> list[dict]:
    """Fetch and parse intern jobs from Netflix."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(NETFLIX_JOBS_API, params=NETFLIX_PARAMS)
        resp.raise_for_status()
        return parse_netflix_jobs(resp.json())


async def poll_all() -> list[dict]:
    """Fetch Netflix intern postings. Returns empty list on failure."""
    try:
        return await fetch_jobs()
    except Exception:
        return []
