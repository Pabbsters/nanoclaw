"""Tests for sources/reddit module."""

from __future__ import annotations

import pytest

from sources.reddit import parse_subreddit_response


# ── Mock data matching real Reddit JSON API format ────────────────────

MOCK_REDDIT_RESPONSE: dict = {
    "data": {
        "children": [
            {
                "data": {
                    "name": "t3_abc123",
                    "title": "Google SWE Intern - Got an offer!",
                    "permalink": "/r/csMajors/comments/abc123/google_swe_intern/",
                    "selftext": "Just got my offer for Summer 2026. Happy to share my prep strategy.",
                    "score": 150,
                }
            },
            {
                "data": {
                    "name": "t3_def456",
                    "title": "Meta internship timeline?",
                    "permalink": "/r/csMajors/comments/def456/meta_internship/",
                    "selftext": "",
                    "score": 3,
                }
            },
            {
                "data": {
                    "name": "t3_ghi789",
                    "title": "Intern comp comparison 2026",
                    "permalink": "/r/csMajors/comments/ghi789/intern_comp/",
                    "selftext": "Here are the numbers I collected. " * 30,
                    "score": 500,
                }
            },
        ]
    }
}


class TestParseSubredditResponse:
    """Test parsing of Reddit JSON responses."""

    def test_parses_all_posts(self) -> None:
        results = parse_subreddit_response("csMajors", MOCK_REDDIT_RESPONSE)
        assert len(results) == 3

    def test_correct_field_mapping(self) -> None:
        results = parse_subreddit_response("csMajors", MOCK_REDDIT_RESPONSE)
        first = results[0]
        assert first["posting_id"] == "t3_abc123"
        assert first["title"] == "Google SWE Intern - Got an offer!"
        assert first["company_slug"] == "csmajors"
        assert first["company_name"] == "r/csMajors"
        assert first["score"] == 150

    def test_url_construction(self) -> None:
        results = parse_subreddit_response("csMajors", MOCK_REDDIT_RESPONSE)
        assert results[0]["url"] == (
            "https://www.reddit.com/r/csMajors/comments/abc123/google_swe_intern/"
        )

    def test_description_from_selftext(self) -> None:
        results = parse_subreddit_response("csMajors", MOCK_REDDIT_RESPONSE)
        assert "offer" in results[0]["description"]

    def test_empty_selftext(self) -> None:
        results = parse_subreddit_response("csMajors", MOCK_REDDIT_RESPONSE)
        assert results[1]["description"] == ""

    def test_description_truncated(self) -> None:
        results = parse_subreddit_response("csMajors", MOCK_REDDIT_RESPONSE)
        assert len(results[2]["description"]) <= 500

    def test_score_preserved(self) -> None:
        results = parse_subreddit_response("csMajors", MOCK_REDDIT_RESPONSE)
        scores = [r["score"] for r in results]
        assert scores == [150, 3, 500]

    def test_empty_children(self) -> None:
        results = parse_subreddit_response("test", {"data": {"children": []}})
        assert results == []

    def test_missing_data_key(self) -> None:
        results = parse_subreddit_response("test", {})
        assert results == []

    def test_location_is_empty(self) -> None:
        results = parse_subreddit_response("csMajors", MOCK_REDDIT_RESPONSE)
        for r in results:
            assert r["location"] == ""
