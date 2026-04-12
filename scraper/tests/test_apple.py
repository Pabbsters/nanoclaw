"""Tests for sources/apple module."""

from __future__ import annotations

import pytest

from sources.apple import parse_apple_jobs


# ── Mock data matching real Apple Jobs API format ─────────────────────

MOCK_APPLE_RESPONSE: dict = {
    "searchResults": [
        {
            "positionId": "200554321",
            "postingTitle": "Software Engineering Intern",
            "locations": [
                {"name": "Cupertino, CA"},
                {"name": "Austin, TX"},
            ],
            "transformedPostingUrl": "/en-us/details/200554321/software-engineering-intern",
        },
        {
            "positionId": "200554322",
            "postingTitle": "Machine Learning Intern",
            "locations": [{"name": "Seattle, WA"}],
            "transformedPostingUrl": "/en-us/details/200554322/machine-learning-intern",
        },
        {
            "positionId": "200554323",
            "postingTitle": "Hardware Engineering Intern",
            "locations": [],
            "transformedPostingUrl": "",
        },
    ]
}


class TestParseAppleJobs:
    """Test parsing of Apple Jobs API responses."""

    def test_parses_all_jobs(self) -> None:
        results = parse_apple_jobs(MOCK_APPLE_RESPONSE)
        assert len(results) == 3

    def test_correct_field_mapping(self) -> None:
        results = parse_apple_jobs(MOCK_APPLE_RESPONSE)
        swe = results[0]
        assert swe["posting_id"] == "200554321"
        assert swe["title"] == "Software Engineering Intern"
        assert swe["company_slug"] == "apple"
        assert swe["company_name"] == "Apple"
        assert swe["skills"] == ""
        assert swe["team"] == ""

    def test_multiple_locations_joined(self) -> None:
        results = parse_apple_jobs(MOCK_APPLE_RESPONSE)
        swe = results[0]
        assert "Cupertino, CA" in swe["location"]
        assert "Austin, TX" in swe["location"]

    def test_single_location(self) -> None:
        results = parse_apple_jobs(MOCK_APPLE_RESPONSE)
        ml = results[1]
        assert ml["location"] == "Seattle, WA"

    def test_empty_locations(self) -> None:
        results = parse_apple_jobs(MOCK_APPLE_RESPONSE)
        hw = results[2]
        assert hw["location"] == ""

    def test_url_construction(self) -> None:
        results = parse_apple_jobs(MOCK_APPLE_RESPONSE)
        assert results[0]["url"] == (
            "https://jobs.apple.com"
            "/en-us/details/200554321/software-engineering-intern"
        )

    def test_empty_url_gives_empty_string(self) -> None:
        results = parse_apple_jobs(MOCK_APPLE_RESPONSE)
        assert results[2]["url"] == ""

    def test_empty_search_results(self) -> None:
        results = parse_apple_jobs({"searchResults": []})
        assert results == []

    def test_missing_key(self) -> None:
        results = parse_apple_jobs({})
        assert results == []

    def test_posting_id_is_string(self) -> None:
        results = parse_apple_jobs(MOCK_APPLE_RESPONSE)
        for r in results:
            assert isinstance(r["posting_id"], str)
