"""Tests for sources/lever module."""

from __future__ import annotations

import pytest

from sources.lever import is_intern_posting, parse_lever_jobs


# ── Mock data matching real Lever API format ──────────────────────────

MOCK_LEVER_RESPONSE: list = [
    {
        "id": "lev-001",
        "text": "Software Engineering Intern - Summer 2026",
        "hostedUrl": "https://jobs.lever.co/netflix/lev-001",
        "categories": {
            "team": "Core Platform",
            "department": "Engineering",
            "location": "Los Gatos, CA",
        },
        "descriptionPlain": "Java, microservices, distributed systems. Netflix scale.",
    },
    {
        "id": "lev-002",
        "text": "Staff Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/netflix/lev-002",
        "categories": {
            "team": "Streaming",
            "department": "Engineering",
            "location": "Remote",
        },
        "descriptionPlain": "10+ years. System design expertise.",
    },
    {
        "id": "lev-003",
        "text": "Data Engineering Co-op",
        "hostedUrl": "https://jobs.lever.co/netflix/lev-003",
        "categories": {
            "team": "",
            "department": "Data",
            "location": "New York, NY",
        },
        "descriptionPlain": "Spark, Airflow, Python. Build data pipelines.",
    },
    {
        "id": "lev-004",
        "text": "Product Design Internship",
        "hostedUrl": "https://jobs.lever.co/netflix/lev-004",
        "categories": {},
        "descriptionPlain": "",
    },
]


class TestIsInternPosting:
    """Test intern title pattern matching."""

    def test_matches_intern(self) -> None:
        assert is_intern_posting("Software Engineering Intern - Summer 2026") is True

    def test_matches_coop(self) -> None:
        assert is_intern_posting("Data Engineering Co-op") is True

    def test_matches_internship(self) -> None:
        assert is_intern_posting("Product Design Internship") is True

    def test_rejects_staff(self) -> None:
        assert is_intern_posting("Staff Backend Engineer") is False


class TestParseLeverJobs:
    """Test parsing of Lever API responses."""

    def test_filters_to_intern_only(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", MOCK_LEVER_RESPONSE)
        titles = [r["title"] for r in results]
        assert "Software Engineering Intern - Summer 2026" in titles
        assert "Data Engineering Co-op" in titles
        assert "Product Design Internship" in titles
        assert "Staff Backend Engineer" not in titles

    def test_correct_count(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", MOCK_LEVER_RESPONSE)
        assert len(results) == 3

    def test_correct_field_mapping(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", MOCK_LEVER_RESPONSE)
        intern = next(r for r in results if r["posting_id"] == "lev-001")
        assert intern["title"] == "Software Engineering Intern - Summer 2026"
        assert intern["url"] == "https://jobs.lever.co/netflix/lev-001"
        assert intern["company_slug"] == "netflix"
        assert intern["company_name"] == "Netflix"
        assert intern["team"] == "Core Platform"
        assert intern["location"] == "Los Gatos, CA"

    def test_skills_from_description(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", MOCK_LEVER_RESPONSE)
        intern = next(r for r in results if r["posting_id"] == "lev-001")
        assert "Java" in intern["skills"]
        assert "Netflix" in intern["skills"]

    def test_empty_team_falls_back_to_department(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", MOCK_LEVER_RESPONSE)
        coop = next(r for r in results if r["posting_id"] == "lev-003")
        assert coop["team"] == "Data"

    def test_empty_categories(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", MOCK_LEVER_RESPONSE)
        design = next(r for r in results if r["posting_id"] == "lev-004")
        assert design["team"] == ""
        assert design["location"] == ""

    def test_empty_description_gives_empty_skills(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", MOCK_LEVER_RESPONSE)
        design = next(r for r in results if r["posting_id"] == "lev-004")
        assert design["skills"] == ""

    def test_posting_id_is_string(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", MOCK_LEVER_RESPONSE)
        for r in results:
            assert isinstance(r["posting_id"], str)

    def test_empty_list(self) -> None:
        results = parse_lever_jobs("netflix", "Netflix", [])
        assert results == []
