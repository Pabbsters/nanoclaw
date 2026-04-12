"""Tests for sources/ashby module."""

from __future__ import annotations

import pytest

from sources.ashby import is_intern_posting, parse_ashby_jobs


# ── Mock data matching Ashby API format ───────────────────────────────

MOCK_ASHBY_DICT_RESPONSE: dict = {
    "jobs": [
        {
            "id": "abc-001",
            "title": "ML Engineering Intern",
            "departmentName": "Research",
            "location": "San Francisco, CA",
            "descriptionPlain": "PyTorch, transformers, RLHF experience.",
            "hostedUrl": "https://jobs.ashbyhq.com/anthropic/abc-001",
        },
        {
            "id": "abc-002",
            "title": "Senior Research Scientist",
            "departmentName": "Alignment",
            "location": "Remote",
            "descriptionPlain": "PhD required. 5+ years experience.",
            "hostedUrl": "https://jobs.ashbyhq.com/anthropic/abc-002",
        },
        {
            "id": "abc-003",
            "title": "Software Engineering Apprentice",
            "departmentName": "",
            "location": {"name": "London, UK"},
            "descriptionPlain": "",
            "hostedUrl": "https://jobs.ashbyhq.com/anthropic/abc-003",
        },
    ]
}

MOCK_ASHBY_LIST_RESPONSE: list = [
    {
        "id": "xyz-001",
        "title": "Data Science Internship",
        "team": "Analytics",
        "location": "NYC",
        "description": "SQL, Python, dashboards.",
        "jobUrl": "https://jobs.ashbyhq.com/openai/xyz-001",
    },
]


class TestIsInternPosting:
    """Test intern title pattern matching."""

    def test_matches_intern(self) -> None:
        assert is_intern_posting("ML Engineering Intern") is True

    def test_matches_apprentice(self) -> None:
        assert is_intern_posting("Software Engineering Apprentice") is True

    def test_rejects_senior(self) -> None:
        assert is_intern_posting("Senior Research Scientist") is False


class TestParseAshbyJobsDictFormat:
    """Test parsing when response is a dict with 'jobs' key."""

    def test_filters_to_intern_only(self) -> None:
        results = parse_ashby_jobs("anthropic", "Anthropic", MOCK_ASHBY_DICT_RESPONSE)
        titles = [r["title"] for r in results]
        assert "ML Engineering Intern" in titles
        assert "Software Engineering Apprentice" in titles
        assert "Senior Research Scientist" not in titles

    def test_correct_field_mapping(self) -> None:
        results = parse_ashby_jobs("anthropic", "Anthropic", MOCK_ASHBY_DICT_RESPONSE)
        intern = next(r for r in results if r["posting_id"] == "abc-001")
        assert intern["title"] == "ML Engineering Intern"
        assert intern["url"] == "https://jobs.ashbyhq.com/anthropic/abc-001"
        assert intern["company_slug"] == "anthropic"
        assert intern["company_name"] == "Anthropic"
        assert intern["team"] == "Research"

    def test_skills_from_description(self) -> None:
        results = parse_ashby_jobs("anthropic", "Anthropic", MOCK_ASHBY_DICT_RESPONSE)
        intern = next(r for r in results if r["posting_id"] == "abc-001")
        assert "PyTorch" in intern["skills"]

    def test_empty_description_gives_empty_skills(self) -> None:
        results = parse_ashby_jobs("anthropic", "Anthropic", MOCK_ASHBY_DICT_RESPONSE)
        apprentice = next(r for r in results if r["posting_id"] == "abc-003")
        assert apprentice["skills"] == ""

    def test_location_dict_parsed(self) -> None:
        results = parse_ashby_jobs("anthropic", "Anthropic", MOCK_ASHBY_DICT_RESPONSE)
        apprentice = next(r for r in results if r["posting_id"] == "abc-003")
        assert apprentice["location"] == "London, UK"

    def test_location_string_preserved(self) -> None:
        results = parse_ashby_jobs("anthropic", "Anthropic", MOCK_ASHBY_DICT_RESPONSE)
        intern = next(r for r in results if r["posting_id"] == "abc-001")
        assert intern["location"] == "San Francisco, CA"


class TestParseAshbyJobsListFormat:
    """Test parsing when response is a root-level array."""

    def test_parses_list_format(self) -> None:
        results = parse_ashby_jobs("openai", "OpenAI", MOCK_ASHBY_LIST_RESPONSE)
        assert len(results) == 1
        assert results[0]["title"] == "Data Science Internship"

    def test_falls_back_to_team_key(self) -> None:
        results = parse_ashby_jobs("openai", "OpenAI", MOCK_ASHBY_LIST_RESPONSE)
        assert results[0]["team"] == "Analytics"

    def test_falls_back_to_description_key(self) -> None:
        results = parse_ashby_jobs("openai", "OpenAI", MOCK_ASHBY_LIST_RESPONSE)
        assert "SQL" in results[0]["skills"]

    def test_falls_back_to_jobUrl(self) -> None:
        results = parse_ashby_jobs("openai", "OpenAI", MOCK_ASHBY_LIST_RESPONSE)
        assert results[0]["url"] == "https://jobs.ashbyhq.com/openai/xyz-001"


class TestParseAshbyJobsEdgeCases:
    """Edge case tests."""

    def test_empty_jobs_dict(self) -> None:
        results = parse_ashby_jobs("co", "Co", {"jobs": []})
        assert results == []

    def test_empty_list(self) -> None:
        results = parse_ashby_jobs("co", "Co", [])
        assert results == []

    def test_posting_id_is_string(self) -> None:
        results = parse_ashby_jobs("anthropic", "Anthropic", MOCK_ASHBY_DICT_RESPONSE)
        for r in results:
            assert isinstance(r["posting_id"], str)
