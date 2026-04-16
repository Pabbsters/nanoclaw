"""Tests for the active UIUC alumni collector."""

from __future__ import annotations

import json

import pytest

from uiuc_alumni_collector import (
    _promote_candidate,
    _run_browser_assisted_provider,
    build_alumni_collector_queries,
    run_alumni_collector,
)


def test_build_alumni_collector_queries_cover_uiuc_paths() -> None:
    queries = build_alumni_collector_queries()

    assert queries
    assert any("NCSA" in query for query in queries)
    assert any("quant" in query.lower() for query in queries)
    assert all("linkedin.com/in" in query for query in queries)


def test_promote_candidate_filters_low_confidence() -> None:
    promoted = _promote_candidate(
        {
            "provider": "public",
            "profile_url": "https://www.linkedin.com/in/alice-illinois/",
            "name": "Alice Illinois",
            "headline": "UIUC ML researcher at NCSA",
            "snippet": "University of Illinois Urbana-Champaign student doing ML research",
            "path_tags": ["ml_ai_research"],
            "confidence": 0.45,
        }
    )

    assert promoted is None


@pytest.mark.asyncio
async def test_browser_assisted_provider_is_unconfigured_without_export(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UIUC_SCOUT_BROWSER_ASSISTED_EXPORT_PATH", raising=False)
    monkeypatch.delenv("COMPOSIO_UIUC_ALUMNI_EXPORT_PATH", raising=False)
    monkeypatch.delenv("UIUC_SCOUT_BROWSER_ASSISTED_CANDIDATES_PATH", raising=False)

    candidates, status = await _run_browser_assisted_provider()

    assert candidates == []
    assert status["status"] == "unconfigured"


@pytest.mark.asyncio
async def test_run_alumni_collector_writes_batch_and_merged_profiles(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_dir = tmp_path / "alumni-auto"
    merged_path = tmp_path / "alumni_profiles_merged.json"

    async def fake_public_provider(queries: list[str]):
        return (
            [
                {
                    "provider": "public",
                    "query": queries[0],
                    "profile_url": "https://www.linkedin.com/in/alice-illinois/",
                    "name": "Alice Illinois",
                    "headline": "UIUC ML researcher at NCSA",
                    "snippet": "University of Illinois Urbana-Champaign student doing ML research at NCSA",
                    "path_tags": ["ml_ai_research"],
                    "confidence": 0.91,
                    "raw_source_url": "https://example.com/search",
                }
            ],
            {
                "provider": "public",
                "status": "healthy",
                "queries_run": len(queries),
                "blocked_queries": 0,
                "errors": 0,
                "candidates_found": 1,
            },
        )

    async def fake_browser_provider():
        return [], {
            "provider": "browser_assisted",
            "status": "unconfigured",
            "queries_run": 0,
            "blocked_queries": 0,
            "errors": 0,
            "candidates_found": 0,
        }

    monkeypatch.setattr("uiuc_alumni_collector._run_public_provider", fake_public_provider)
    monkeypatch.setattr("uiuc_alumni_collector._run_browser_assisted_provider", fake_browser_provider)
    monkeypatch.setattr("uiuc_alumni_collector._default_auto_output_dir", lambda: auto_dir)
    monkeypatch.setattr("uiuc_alumni_collector._default_merged_path", lambda: merged_path)
    monkeypatch.setattr("uiuc_alumni_collector.load_alumni_profile_records", lambda: [])

    summary = await run_alumni_collector(mode="hybrid")

    batch_files = sorted(auto_dir.glob("alumni-collector-*.json"))
    assert len(batch_files) == 1
    assert summary["profiles_promoted"] == 1
    assert summary["merged_profiles_total"] == 1

    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    assert len(merged["profiles"]) == 1
    assert merged["profiles"][0]["name"] == "Alice Illinois"


@pytest.mark.asyncio
async def test_run_alumni_collector_merges_existing_profiles(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_dir = tmp_path / "alumni-auto"
    merged_path = tmp_path / "alumni_profiles_merged.json"

    async def fake_public_provider(queries: list[str]):
        return (
            [
                {
                    "provider": "public",
                    "query": queries[0],
                    "profile_url": "https://www.linkedin.com/in/alice-illinois/",
                    "name": "Alice Illinois",
                    "headline": "UIUC AI researcher",
                    "snippet": "University of Illinois Urbana-Champaign AI researcher",
                    "path_tags": ["ml_ai_research"],
                    "confidence": 0.9,
                    "raw_source_url": "https://example.com/search",
                }
            ],
            {
                "provider": "public",
                "status": "healthy",
                "queries_run": len(queries),
                "blocked_queries": 0,
                "errors": 0,
                "candidates_found": 1,
            },
        )

    async def fake_browser_provider():
        return [], {
            "provider": "browser_assisted",
            "status": "unconfigured",
            "queries_run": 0,
            "blocked_queries": 0,
            "errors": 0,
            "candidates_found": 0,
        }

    existing_profile = {
        "profile_url": "https://www.linkedin.com/in/bob-illinois/",
        "name": "Bob Illinois",
        "headline": "UIUC quant student",
        "education_matches_uiuc": True,
        "path_tags": ["quant_fintech"],
    }

    monkeypatch.setattr("uiuc_alumni_collector._run_public_provider", fake_public_provider)
    monkeypatch.setattr("uiuc_alumni_collector._run_browser_assisted_provider", fake_browser_provider)
    monkeypatch.setattr("uiuc_alumni_collector._default_auto_output_dir", lambda: auto_dir)
    monkeypatch.setattr("uiuc_alumni_collector._default_merged_path", lambda: merged_path)
    monkeypatch.setattr("uiuc_alumni_collector.load_alumni_profile_records", lambda: [existing_profile])

    summary = await run_alumni_collector(mode="hybrid")

    merged = json.loads(merged_path.read_text(encoding="utf-8"))
    names = {profile["name"] for profile in merged["profiles"]}
    assert summary["merged_profiles_total"] == 2
    assert names == {"Alice Illinois", "Bob Illinois"}
