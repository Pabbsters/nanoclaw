"""Tests for sources/amazon module."""

from __future__ import annotations

import pytest

from sources.amazon import parse_amazon_jobs


# ── Mock data matching real Amazon Jobs API format ────────────────────

MOCK_AMAZON_RESPONSE: dict = {
    "jobs": [
        {
            "id_icims": "2024-ABC123",
            "title": "Software Dev Engineer Intern",
            "basic_qualifications": "Currently enrolled in CS program. Python, Java.",
            "preferred_qualifications": "AWS experience preferred.",
            "job_path": "/en/jobs/2024-ABC123/software-dev-engineer-intern",
            "normalized_location": "Seattle, WA",
        },
        {
            "id_icims": "2024-DEF456",
            "title": "Data Engineer Intern",
            "basic_qualifications": "SQL, Python, data pipelines.",
            "preferred_qualifications": None,
            "job_path": "/en/jobs/2024-DEF456/data-engineer-intern",
            "normalized_location": "Arlington, VA",
        },
        {
            "id_icims": "2024-GHI789",
            "title": "Applied Scientist Intern",
            "basic_qualifications": "",
            "preferred_qualifications": "PhD in ML or related field.",
            "job_path": "",
            "normalized_location": "New York, NY",
        },
    ]
}


class TestParseAmazonJobs:
    """Test parsing of Amazon Jobs API responses."""

    def test_parses_all_jobs(self) -> None:
        results = parse_amazon_jobs(MOCK_AMAZON_RESPONSE)
        assert len(results) == 3

    def test_correct_field_mapping(self) -> None:
        results = parse_amazon_jobs(MOCK_AMAZON_RESPONSE)
        sde = results[0]
        assert sde["posting_id"] == "2024-ABC123"
        assert sde["title"] == "Software Dev Engineer Intern"
        assert sde["company_slug"] == "amazon"
        assert sde["company_name"] == "Amazon"
        assert sde["location"] == "Seattle, WA"
        assert "Python" in sde["skills"]

    def test_url_construction(self) -> None:
        results = parse_amazon_jobs(MOCK_AMAZON_RESPONSE)
        assert results[0]["url"] == (
            "https://www.amazon.jobs"
            "/en/jobs/2024-ABC123/software-dev-engineer-intern"
        )

    def test_empty_job_path_gives_empty_url(self) -> None:
        results = parse_amazon_jobs(MOCK_AMAZON_RESPONSE)
        assert results[2]["url"] == ""

    def test_none_basic_qualifications(self) -> None:
        results = parse_amazon_jobs(MOCK_AMAZON_RESPONSE)
        data_eng = results[1]
        assert "SQL" in data_eng["skills"]

    def test_empty_basic_qualifications(self) -> None:
        results = parse_amazon_jobs(MOCK_AMAZON_RESPONSE)
        scientist = results[2]
        assert scientist["skills"] == ""

    def test_empty_jobs_list(self) -> None:
        results = parse_amazon_jobs({"jobs": []})
        assert results == []

    def test_missing_jobs_key(self) -> None:
        results = parse_amazon_jobs({})
        assert results == []

    def test_posting_id_is_string(self) -> None:
        results = parse_amazon_jobs(MOCK_AMAZON_RESPONSE)
        for r in results:
            assert isinstance(r["posting_id"], str)
