"""Tests for sources/greenhouse module."""

from __future__ import annotations

import pytest

from sources.greenhouse import is_intern_posting, parse_greenhouse_jobs


# ── Mock data matching real Greenhouse API format ─────────────────────

MOCK_GREENHOUSE_RESPONSE: dict = {
    "jobs": [
        {
            "id": 101,
            "title": "Software Engineering Intern",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/101",
            "content": "<p>Python, Java, distributed systems experience preferred.</p>",
            "departments": [{"name": "Engineering"}],
            "location": {"name": "New York, NY"},
        },
        {
            "id": 102,
            "title": "Senior Software Engineer",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/102",
            "content": "<p>10+ years experience required.</p>",
            "departments": [{"name": "Platform"}],
            "location": {"name": "San Francisco, CA"},
        },
        {
            "id": 103,
            "title": "Data Science Co-op",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/103",
            "content": "<p>R, SQL, Tableau. Statistical modeling.</p>",
            "departments": [],
            "location": {"name": "Remote"},
        },
        {
            "id": 104,
            "title": "ML Research Fellow",
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/104",
            "content": "",
            "departments": [{"name": "AI Research"}, {"name": "Labs"}],
            "location": {"name": "Seattle, WA"},
        },
    ]
}


class TestIsInternPosting:
    """Test intern title pattern matching."""

    @pytest.mark.parametrize(
        "title",
        [
            "Software Engineering Intern",
            "ML Internship - Summer 2026",
            "Data Science Co-op",
            "Research Fellow",
            "DevOps Apprentice",
            "Cloud Engineering Residency",
        ],
    )
    def test_matches_intern_patterns(self, title: str) -> None:
        assert is_intern_posting(title) is True

    @pytest.mark.parametrize(
        "title",
        [
            "Senior Software Engineer",
            "Staff ML Engineer",
            "Engineering Manager",
            "Director of Product",
            "Internal Tools Engineer",
        ],
    )
    def test_rejects_non_intern_titles(self, title: str) -> None:
        assert is_intern_posting(title) is False

    def test_case_insensitive(self) -> None:
        assert is_intern_posting("SOFTWARE ENGINEERING INTERN") is True
        assert is_intern_posting("ml INTERNSHIP") is True


class TestParseGreenhouseJobs:
    """Test parsing of Greenhouse API responses."""

    def test_filters_to_intern_postings_only(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", MOCK_GREENHOUSE_RESPONSE)
        titles = [r["title"] for r in results]
        assert "Software Engineering Intern" in titles
        assert "Data Science Co-op" in titles
        assert "ML Research Fellow" in titles
        assert "Senior Software Engineer" not in titles

    def test_correct_field_mapping(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", MOCK_GREENHOUSE_RESPONSE)
        intern = next(r for r in results if r["posting_id"] == "101")
        assert intern["title"] == "Software Engineering Intern"
        assert intern["url"] == "https://boards.greenhouse.io/acme/jobs/101"
        assert intern["company_slug"] == "acme"
        assert intern["company_name"] == "Acme Inc"
        assert intern["team"] == "Engineering"
        assert intern["location"] == "New York, NY"

    def test_skills_from_content(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", MOCK_GREENHOUSE_RESPONSE)
        intern = next(r for r in results if r["posting_id"] == "101")
        assert "Python" in intern["skills"]

    def test_empty_content_gives_empty_skills(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", MOCK_GREENHOUSE_RESPONSE)
        fellow = next(r for r in results if r["posting_id"] == "104")
        assert fellow["skills"] == ""

    def test_empty_departments_gives_empty_team(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", MOCK_GREENHOUSE_RESPONSE)
        coop = next(r for r in results if r["posting_id"] == "103")
        assert coop["team"] == ""

    def test_multiple_departments_takes_first(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", MOCK_GREENHOUSE_RESPONSE)
        fellow = next(r for r in results if r["posting_id"] == "104")
        assert fellow["team"] == "AI Research"

    def test_posting_id_is_string(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", MOCK_GREENHOUSE_RESPONSE)
        for r in results:
            assert isinstance(r["posting_id"], str)

    def test_empty_jobs_list(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", {"jobs": []})
        assert results == []

    def test_missing_jobs_key(self) -> None:
        results = parse_greenhouse_jobs("acme", "Acme Inc", {})
        assert results == []
