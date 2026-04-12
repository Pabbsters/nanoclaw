"""GitHub repo poller for internship listing aggregators."""

from __future__ import annotations

import hashlib
import re

import httpx

from config import GITHUB_REPOS

GITHUB_RAW = "https://raw.githubusercontent.com/{repo}/main/README.md"

# Matches markdown table rows: | Company | Role | Location | Link | Date |
TABLE_ROW_RE = re.compile(
    r"^\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|",
    re.MULTILINE,
)

LINK_RE = re.compile(r"\[.*?\]\((https?://[^\s)]+)\)")


def _posting_id(url: str) -> str:
    """Deterministic posting ID from URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _slug_from_name(name: str) -> str:
    """Convert company name to a URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _is_separator_row(cells: list[str]) -> bool:
    """Check if row is a markdown table separator (--- | --- | ---)."""
    return all(c.strip().replace("-", "").replace(":", "") == "" for c in cells)


def parse_readme_table(readme: str) -> list[dict]:
    """Parse internship listings from a markdown table README.

    Expected format:
    | Company | Role | Location | Application/Link | Date Posted |
    """
    results: list[dict] = []

    for match in TABLE_ROW_RE.finditer(readme):
        cells = [match.group(i).strip() for i in range(1, 6)]

        if _is_separator_row(cells):
            continue

        company_raw, role, location, link_cell, _date = cells

        # Skip header rows
        if company_raw.lower() in ("company", "company name"):
            continue

        # Extract URL from markdown link syntax
        link_match = LINK_RE.search(link_cell)
        url = link_match.group(1) if link_match else ""
        if not url:
            continue

        # Strip markdown formatting from company name
        company_name = re.sub(r"\*\*|<[^>]+>|\[([^\]]*)\]\([^)]*\)", r"\1", company_raw).strip()

        results.append({
            "posting_id": _posting_id(url),
            "title": role.strip(),
            "url": url,
            "company_slug": _slug_from_name(company_name),
            "company_name": company_name,
            "team": "",
            "skills": "",
            "location": location.strip(),
        })

    return results


async def fetch_repo_listings(repo: str) -> list[dict]:
    """Fetch and parse internship listings from a GitHub repo."""
    url = GITHUB_RAW.format(repo=repo)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return parse_readme_table(resp.text)


async def poll_all() -> list[dict]:
    """Fetch from all configured GitHub repos."""
    results: list[dict] = []
    for repo in GITHUB_REPOS:
        try:
            listings = await fetch_repo_listings(repo)
            results.extend(listings)
        except Exception:
            pass
    return results
