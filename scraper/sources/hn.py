"""Hacker News Algolia API poller for intern-related posts."""

from __future__ import annotations

import time

import httpx

ALGOLIA_API = "https://hn.algolia.com/api/v1/search_by_date"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={object_id}"

# Default lookback: 24 hours
DEFAULT_LOOKBACK_SECONDS = 86400


def parse_hn_results(raw: dict) -> list[dict]:
    """Parse HN Algolia search response into normalized posting dicts."""
    hits = raw.get("hits", [])
    results: list[dict] = []

    for hit in hits:
        object_id = hit.get("objectID", "")
        title = hit.get("title") or hit.get("story_title") or ""
        author = hit.get("author", "")
        comment_text = hit.get("comment_text", "") or ""

        url = hit.get("url") or HN_ITEM_URL.format(object_id=object_id)

        # Use comment text or story text as description
        description = comment_text[:500] if comment_text else ""

        results.append({
            "posting_id": str(object_id),
            "title": title if title else f"HN comment by {author}",
            "url": url,
            "company_slug": "hackernews",
            "company_name": "Hacker News",
            "team": "",
            "skills": "",
            "location": "",
            "description": description,
        })

    return results


async def fetch_hiring_posts(
    query: str = "intern",
    lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS,
) -> list[dict]:
    """Search HN for intern-related posts."""
    since_ts = int(time.time()) - lookback_seconds
    params = {
        "query": query,
        "tags": "comment",
        "numericFilters": f"created_at_i>{since_ts}",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(ALGOLIA_API, params=params)
        resp.raise_for_status()
        return parse_hn_results(resp.json())


async def poll_all() -> list[dict]:
    """Fetch intern-related HN posts."""
    try:
        return await fetch_hiring_posts()
    except Exception:
        return []
