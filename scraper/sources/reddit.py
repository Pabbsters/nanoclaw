"""Reddit JSON API poller for internship-related posts."""

from __future__ import annotations

import asyncio

import httpx

from config import SUBREDDITS

USER_AGENT = "jojo-scraper/1.0"
REDDIT_BASE = "https://www.reddit.com"
DELAY_SECONDS = 2


def parse_subreddit_response(subreddit: str, raw: dict) -> list[dict]:
    """Parse Reddit listing JSON into normalized posting dicts."""
    children = raw.get("data", {}).get("children", [])
    results: list[dict] = []

    for child in children:
        post = child.get("data", {})
        post_id = post.get("name", "")  # e.g. t3_xxx
        title = post.get("title", "")
        permalink = post.get("permalink", "")
        selftext = post.get("selftext", "")
        score = post.get("score", 0)

        url = f"{REDDIT_BASE}{permalink}" if permalink else ""

        results.append({
            "posting_id": post_id,
            "title": title,
            "url": url,
            "company_slug": subreddit.lower(),
            "company_name": f"r/{subreddit}",
            "description": selftext[:500],
            "skills": "",
            "team": "",
            "location": "",
            "score": score,
        })

    return results


async def fetch_subreddit_posts(
    subreddit: str, limit: int = 25
) -> list[dict]:
    """Fetch recent posts from a subreddit."""
    url = f"{REDDIT_BASE}/r/{subreddit}/new.json"
    headers = {"User-Agent": USER_AGENT}
    params = {"limit": str(limit)}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return parse_subreddit_response(subreddit, resp.json())


async def poll_all(min_score: int = 5) -> list[dict]:
    """Fetch from all subreddits, filter by minimum score."""
    results: list[dict] = []

    for subreddit in SUBREDDITS:
        try:
            posts = await fetch_subreddit_posts(subreddit)
            filtered = [p for p in posts if p.get("score", 0) >= min_score]
            results.extend(filtered)
        except Exception:
            pass
        await asyncio.sleep(DELAY_SECONDS)

    return results
