"""Tests for sources/hn module."""

from __future__ import annotations

import pytest

from sources.hn import parse_hn_results


# ── Mock data matching real HN Algolia API format ─────────────────────

MOCK_HN_RESPONSE: dict = {
    "hits": [
        {
            "objectID": "40001234",
            "title": "Who is hiring? (January 2026)",
            "url": "https://news.ycombinator.com/item?id=40001234",
            "author": "whoishiring",
            "comment_text": None,
        },
        {
            "objectID": "40005678",
            "title": None,
            "story_title": "Who is hiring? (January 2026)",
            "url": None,
            "author": "startup_ceo",
            "comment_text": (
                "Acme Corp | ML Intern | Remote | "
                "We're looking for ML interns to work on LLM fine-tuning."
            ),
        },
        {
            "objectID": "40009012",
            "title": "",
            "story_title": "",
            "url": None,
            "author": "anon_poster",
            "comment_text": "Short comment about internships. " * 30,
        },
    ]
}


class TestParseHnResults:
    """Test parsing of HN Algolia API responses."""

    def test_parses_all_hits(self) -> None:
        results = parse_hn_results(MOCK_HN_RESPONSE)
        assert len(results) == 3

    def test_story_with_title_and_url(self) -> None:
        results = parse_hn_results(MOCK_HN_RESPONSE)
        story = results[0]
        assert story["posting_id"] == "40001234"
        assert story["title"] == "Who is hiring? (January 2026)"
        assert story["url"] == "https://news.ycombinator.com/item?id=40001234"
        assert story["company_slug"] == "hackernews"
        assert story["company_name"] == "Hacker News"

    def test_comment_uses_story_title(self) -> None:
        results = parse_hn_results(MOCK_HN_RESPONSE)
        comment = results[1]
        assert comment["title"] == "Who is hiring? (January 2026)"

    def test_comment_text_as_description(self) -> None:
        results = parse_hn_results(MOCK_HN_RESPONSE)
        comment = results[1]
        assert "ML Intern" in comment["description"]

    def test_fallback_url_to_hn_item(self) -> None:
        results = parse_hn_results(MOCK_HN_RESPONSE)
        comment = results[1]
        assert comment["url"] == "https://news.ycombinator.com/item?id=40005678"

    def test_empty_title_fallback_to_author(self) -> None:
        results = parse_hn_results(MOCK_HN_RESPONSE)
        anon = results[2]
        assert anon["title"] == "HN comment by anon_poster"

    def test_description_truncated(self) -> None:
        results = parse_hn_results(MOCK_HN_RESPONSE)
        anon = results[2]
        assert len(anon["description"]) <= 500

    def test_empty_hits(self) -> None:
        results = parse_hn_results({"hits": []})
        assert results == []

    def test_missing_hits_key(self) -> None:
        results = parse_hn_results({})
        assert results == []

    def test_all_have_required_keys(self) -> None:
        results = parse_hn_results(MOCK_HN_RESPONSE)
        required = {"posting_id", "title", "url", "company_slug", "company_name"}
        for r in results:
            assert required.issubset(r.keys())
