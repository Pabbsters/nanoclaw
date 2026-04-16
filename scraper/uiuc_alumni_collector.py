"""Active alumni-intel collector for the UIUC scout."""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx

from uiuc_alumni import load_alumni_profile_records
from uiuc_alumni import normalize_linkedin_profile_record


COLLECTOR_QUERY_RESOURCES: tuple[str, ...] = (
    "NCSA",
    "Research Park",
    "PURE",
    "SPIN",
    "REU",
    "Digital Agriculture",
    "AIFARMS",
    "Carle Illinois",
)

COLLECTOR_QUERY_PATHS: tuple[str, ...] = (
    "machine learning",
    "nlp",
    "computer vision",
    "research engineer",
    "data science",
    "software engineer",
    "quant",
    "trading",
    "fintech",
)

LINKEDIN_URL_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9%_\-]+/?", re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"\[(?P<label>[^\]]+)\]\((?P<url>https?://[^)]+)\)")
STATUS_BLOCK_PATTERNS: tuple[str, ...] = (
    "one last step",
    "challenge below",
    "unable to process this search",
    "about this page",
    "too many requests",
)

LAST_COLLECTOR_SUMMARY: dict[str, Any] = {}
PUBLIC_PROVIDER_CONCURRENCY = 4


def _default_auto_output_dir() -> Path:
    return Path.home() / "Vault" / "NanoClaw" / "uiuc-scout" / "input" / "alumni-auto"


def _default_merged_path() -> Path:
    return Path.home() / "Vault" / "NanoClaw" / "uiuc-scout" / "alumni_profiles_merged.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_alumni_collector_queries() -> list[str]:
    queries: list[str] = []
    for resource in COLLECTOR_QUERY_RESOURCES:
        for path in COLLECTOR_QUERY_PATHS:
            queries.append(
                f'site:linkedin.com/in ("University of Illinois Urbana-Champaign" OR UIUC) "{resource}" "{path}"'
            )
    return queries


def _candidate_confidence(candidate: dict[str, Any]) -> float:
    text = " ".join(
        [
            str(candidate.get("name") or ""),
            str(candidate.get("headline") or ""),
            str(candidate.get("snippet") or ""),
            " ".join(candidate.get("path_tags", []) or []),
        ]
    ).lower()
    score = 0.45
    if "illinois" in text or "uiuc" in text:
        score += 0.18
    if any(token in text for token in ("ncsa", "research park", "pure", "spin", "reu", "carle", "aifarms")):
        score += 0.14
    if any(token in text for token in ("machine learning", "nlp", "vision", "research engineer", "software engineer", "quant", "trading", "fintech")):
        score += 0.14
    return round(min(score, 0.95), 2)


def _path_tags_from_query(query: str) -> list[str]:
    lowered = query.lower()
    tags: list[str] = []
    if any(token in lowered for token in ("machine learning", "nlp", "computer vision", "research engineer")):
        tags.append("ml_ai_research")
    if any(token in lowered for token in ("software engineer", "data science")):
        tags.append("uiuc_technical_swe")
    if any(token in lowered for token in ("quant", "trading", "fintech")):
        tags.append("quant_fintech")
    return tags


def _blocked_text(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in STATUS_BLOCK_PATTERNS)


def _extract_candidates_from_markdown(markdown: str, query: str, raw_source_url: str) -> list[dict[str, Any]]:
    path_tags = _path_tags_from_query(query)
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for match in MARKDOWN_LINK_RE.finditer(markdown):
        url = match.group("url")
        if not LINKEDIN_URL_RE.search(url):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        label = match.group("label").strip()
        name = label.split(" | ")[0].split(" - ")[0].strip()
        candidates.append(
            {
                "provider": "public",
                "query": query,
                "profile_url": url,
                "name": name,
                "headline": label,
                "snippet": label,
                "discovered_at": _now_iso(),
                "path_tags": path_tags,
                "confidence": _candidate_confidence(
                    {
                        "name": name,
                        "headline": label,
                        "snippet": label,
                        "path_tags": path_tags,
                    }
                ),
                "raw_source_url": raw_source_url,
            }
        )

    for url in LINKEDIN_URL_RE.findall(markdown):
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append(
            {
                "provider": "public",
                "query": query,
                "profile_url": url,
                "name": "",
                "headline": "",
                "snippet": "",
                "discovered_at": _now_iso(),
                "path_tags": path_tags,
                "confidence": _candidate_confidence({"path_tags": path_tags}),
                "raw_source_url": raw_source_url,
            }
        )

    return candidates


async def _run_public_provider(queries: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    async def fetch_query(
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        query: str,
    ) -> tuple[str, list[dict[str, Any]], str]:
        async with semaphore:
            search_url = f"https://r.jina.ai/http://www.bing.com/search?q={quote_plus(query)}"
            try:
                response = await client.get(search_url, headers={"User-Agent": "Mozilla/5.0"})
                text = response.text
            except Exception:
                return query, [], "error"

            if response.status_code >= 400 or _blocked_text(text):
                return query, [], "blocked"

            return query, _extract_candidates_from_markdown(text, query, search_url), "healthy"

    blocked_queries = 0
    errors = 0
    candidates: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        semaphore = asyncio.Semaphore(PUBLIC_PROVIDER_CONCURRENCY)
        results = await asyncio.gather(
            *(fetch_query(client, semaphore, query) for query in queries)
        )

    for _, query_candidates, status in results:
        if status == "blocked":
            blocked_queries += 1
            continue
        if status == "error":
            errors += 1
            continue
        candidates.extend(query_candidates)

    status = "healthy"
    if blocked_queries and not candidates:
        status = "blocked"
    elif errors and not candidates:
        status = "error"
    elif blocked_queries:
        status = "rate_limited"

    return candidates, {
        "provider": "public",
        "status": status,
        "queries_run": len(queries),
        "blocked_queries": blocked_queries,
        "errors": errors,
        "candidates_found": len(candidates),
    }


def _browser_assisted_env_path() -> Path | None:
    path = (
        os.environ.get("UIUC_SCOUT_BROWSER_ASSISTED_EXPORT_PATH")
        or os.environ.get("COMPOSIO_UIUC_ALUMNI_EXPORT_PATH")
        or os.environ.get("UIUC_SCOUT_BROWSER_ASSISTED_CANDIDATES_PATH")
    )
    return Path(path).expanduser() if path else None


def _load_browser_assisted_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        items = payload.get("candidates") or payload.get("profiles") or payload.get("items") or []
    elif isinstance(payload, list):
        items = payload
    else:
        items = []
    return [dict(item) for item in items if isinstance(item, dict)]


async def _run_browser_assisted_provider() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = _browser_assisted_env_path()
    if path is None or not path.exists():
        return [], {
            "provider": "browser_assisted",
            "status": "unconfigured",
            "queries_run": 0,
            "blocked_queries": 0,
            "errors": 0,
            "candidates_found": 0,
        }

    candidates = _load_browser_assisted_candidates(path)
    return candidates, {
        "provider": "browser_assisted",
        "status": "healthy",
        "queries_run": 0,
        "blocked_queries": 0,
        "errors": 0,
        "candidates_found": len(candidates),
    }


def _promote_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    raw_record = {
        "source": f"{candidate.get('provider', 'public')}_collector",
        "profile_url": candidate.get("profile_url", ""),
        "name": candidate.get("name", ""),
        "headline": candidate.get("headline") or candidate.get("snippet") or "",
        "summary": candidate.get("snippet", ""),
        "education": candidate.get("education") or ["University of Illinois Urbana-Champaign"],
        "current_org": candidate.get("current_org", ""),
        "past_orgs": candidate.get("past_orgs", []),
        "research_orgs": candidate.get("research_orgs", []),
        "projects": candidate.get("projects", []),
        "skills": candidate.get("skills", []),
        "resource_signals": candidate.get("resource_signals", []),
        "path_tags": candidate.get("path_tags", []),
        "education_matches_uiuc": candidate.get("education_matches_uiuc", True),
        "confidence": candidate.get("confidence", 0.0),
    }
    promoted = normalize_linkedin_profile_record(raw_record)
    if promoted is None:
        return None
    if float(candidate.get("confidence", 0.0) or 0.0) < 0.6:
        return None
    return promoted


def _persist_collector_batch(
    promoted_profiles: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path | None = None,
) -> Path | None:
    resolved_dir = output_dir or _default_auto_output_dir()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = resolved_dir / f"alumni-collector-{timestamp}.json"
    payload = {
        "profiles": promoted_profiles,
        "candidates": candidates,
        "summary": summary,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_merged_profiles(profiles: list[dict[str, Any]], path: Path | None = None) -> Path:
    resolved_path = path or _default_merged_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps({"profiles": profiles}, indent=2), encoding="utf-8")
    return resolved_path


def _merge_profiles(existing_profiles: list[dict[str, Any]], new_profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for profile in [*existing_profiles, *new_profiles]:
        key = (
            str(profile.get("profile_url", "")).strip().lower(),
            str(profile.get("name", "")).strip().lower(),
        )
        if key == ("", ""):
            continue
        merged_by_key.setdefault(key, profile)
    return list(merged_by_key.values())


async def run_alumni_collector(mode: str = "hybrid") -> dict[str, Any]:
    queries = build_alumni_collector_queries()
    provider_statuses: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    if mode in {"public", "hybrid"}:
        public_candidates, public_status = await _run_public_provider(queries)
        candidates.extend(public_candidates)
        provider_statuses.append(public_status)

    if mode in {"browser_assisted", "hybrid"}:
        browser_candidates, browser_status = await _run_browser_assisted_provider()
        candidates.extend(browser_candidates)
        provider_statuses.append(browser_status)

    promoted_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        promoted = _promote_candidate(candidate)
        if promoted is None:
            continue
        key = (
            str(promoted.get("profile_url", "")).lower(),
            str(promoted.get("name", "")).lower(),
        )
        promoted_by_key.setdefault(key, promoted)

    promoted_profiles = list(promoted_by_key.values())
    existing_profiles = [
        profile
        for profile in load_alumni_profile_records()
        if isinstance(profile, dict)
    ]
    merged_profiles = _merge_profiles(existing_profiles, promoted_profiles)

    summary = {
        "ran_at": _now_iso(),
        "mode": mode,
        "queries_run": sum(int(status.get("queries_run", 0) or 0) for status in provider_statuses),
        "candidates_found": len(candidates),
        "profiles_promoted": len(promoted_profiles),
        "provider_statuses": provider_statuses,
        "errors": [status for status in provider_statuses if status.get("status") in {"blocked", "error", "rate_limited"}],
        "output_dir": str(_default_auto_output_dir()),
        "merged_profiles_path": str(_default_merged_path()),
        "merged_profiles_total": len(merged_profiles),
    }
    batch_path = _persist_collector_batch(promoted_profiles, candidates, summary)
    merged_path = _write_merged_profiles(merged_profiles)
    summary["latest_batch_path"] = str(batch_path) if batch_path else ""
    summary["merged_profiles_path"] = str(merged_path)

    global LAST_COLLECTOR_SUMMARY
    LAST_COLLECTOR_SUMMARY = summary
    return summary


def get_last_collector_summary() -> dict[str, Any]:
    return dict(LAST_COLLECTOR_SUMMARY)
