"""Apple Jobs API poller for intern postings."""

from __future__ import annotations

import httpx

APPLE_SEARCH_URL = "https://jobs.apple.com/api/role/search"
APPLE_BASE = "https://jobs.apple.com"

DEFAULT_PARAMS: dict[str, str] = {
    "key": "intern",
    "location": "united-states",
}


def parse_apple_jobs(raw: dict) -> list[dict]:
    """Parse Apple Jobs search response into normalized posting dicts."""
    search_results = raw.get("searchResults", [])
    results: list[dict] = []

    for role in search_results:
        position_id = str(role.get("positionId", ""))
        title = role.get("postingTitle", "")

        locations_list = role.get("locations", [])
        location = ", ".join(
            loc.get("name", "") for loc in locations_list if loc.get("name")
        )

        transformed_url = role.get("transformedPostingUrl", "")
        url = f"{APPLE_BASE}{transformed_url}" if transformed_url else ""

        results.append({
            "posting_id": position_id,
            "title": title,
            "url": url,
            "company_slug": "apple",
            "company_name": "Apple",
            "team": "",
            "skills": "",
            "location": location,
        })

    return results


async def fetch_jobs() -> list[dict]:
    """Fetch intern postings from Apple Jobs API."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(APPLE_SEARCH_URL, params=DEFAULT_PARAMS)
        resp.raise_for_status()
        return parse_apple_jobs(resp.json())


async def poll_all() -> list[dict]:
    """Fetch Apple intern postings."""
    try:
        return await fetch_jobs()
    except Exception:
        return []
