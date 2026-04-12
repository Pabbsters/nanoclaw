"""Tests for sources/workday module."""

from __future__ import annotations

import pytest

from sources.workday import (
    WORKDAY_COMPANIES,
    is_intern_posting,
    parse_jsonld_jobs,
    _extract_jsonld_postings,
)


# ── Mock HTML with JSON-LD JobPosting data ─────────────────────────────

MOCK_HTML_WITH_JSONLD = """
<html><head>
<script type="application/ld+json">
{
    "@type": "JobPosting",
    "title": "Software Engineering Intern",
    "url": "https://example.com/jobs/101",
    "description": "Python, distributed systems, and cloud experience preferred.",
    "identifier": {"@type": "PropertyValue", "value": "REQ-101"},
    "jobLocation": {
        "@type": "Place",
        "address": {"@type": "PostalAddress", "addressLocality": "Santa Clara, CA"}
    }
}
</script>
<script type="application/ld+json">
{
    "@type": "JobPosting",
    "title": "Senior Staff Engineer",
    "url": "https://example.com/jobs/102",
    "description": "15+ years experience required."
}
</script>
<script type="application/ld+json">
[
    {
        "@type": "JobPosting",
        "title": "ML Research Fellow",
        "url": "https://example.com/jobs/103",
        "description": "PhD required. TensorFlow, PyTorch."
    },
    {
        "@type": "Organization",
        "name": "Acme Corp"
    }
]
</script>
</head><body></body></html>
"""

MOCK_HTML_NO_JSONLD = """
<html><head><title>Careers</title></head>
<body><h1>No structured data here</h1></body></html>
"""

MOCK_HTML_INVALID_JSON = """
<html><head>
<script type="application/ld+json">{invalid json here}</script>
</head><body></body></html>
"""


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
            "Internal Tools Engineer",
        ],
    )
    def test_rejects_non_intern_titles(self, title: str) -> None:
        assert is_intern_posting(title) is False


class TestExtractJsonldPostings:
    """Test JSON-LD extraction from HTML."""

    def test_extracts_single_objects(self) -> None:
        postings = _extract_jsonld_postings(MOCK_HTML_WITH_JSONLD)
        titles = [p.get("title", "") for p in postings]
        assert "Software Engineering Intern" in titles
        assert "Senior Staff Engineer" in titles

    def test_extracts_from_arrays(self) -> None:
        postings = _extract_jsonld_postings(MOCK_HTML_WITH_JSONLD)
        titles = [p.get("title", "") for p in postings]
        assert "ML Research Fellow" in titles

    def test_skips_non_job_posting_types(self) -> None:
        postings = _extract_jsonld_postings(MOCK_HTML_WITH_JSONLD)
        types = [p.get("@type") for p in postings]
        assert "Organization" not in types

    def test_empty_html(self) -> None:
        assert _extract_jsonld_postings("") == []

    def test_no_jsonld_tags(self) -> None:
        assert _extract_jsonld_postings(MOCK_HTML_NO_JSONLD) == []

    def test_invalid_json_is_skipped(self) -> None:
        assert _extract_jsonld_postings(MOCK_HTML_INVALID_JSON) == []


class TestParseJsonldJobs:
    """Test full parsing pipeline from HTML to normalized dicts."""

    def test_filters_to_intern_postings_only(self) -> None:
        results = parse_jsonld_jobs("nvidia", "Nvidia", MOCK_HTML_WITH_JSONLD)
        titles = [r["title"] for r in results]
        assert "Software Engineering Intern" in titles
        assert "ML Research Fellow" in titles
        assert "Senior Staff Engineer" not in titles

    def test_correct_field_mapping(self) -> None:
        results = parse_jsonld_jobs("nvidia", "Nvidia", MOCK_HTML_WITH_JSONLD)
        intern = next(r for r in results if r["title"] == "Software Engineering Intern")
        assert intern["posting_id"] == "REQ-101"
        assert intern["url"] == "https://example.com/jobs/101"
        assert intern["company_slug"] == "nvidia"
        assert intern["company_name"] == "Nvidia"
        assert intern["location"] == "Santa Clara, CA"

    def test_skills_from_description(self) -> None:
        results = parse_jsonld_jobs("nvidia", "Nvidia", MOCK_HTML_WITH_JSONLD)
        intern = next(r for r in results if r["title"] == "Software Engineering Intern")
        assert "Python" in intern["skills"]

    def test_fallback_posting_id_when_no_identifier(self) -> None:
        results = parse_jsonld_jobs("nvidia", "Nvidia", MOCK_HTML_WITH_JSONLD)
        fellow = next(r for r in results if r["title"] == "ML Research Fellow")
        assert fellow["posting_id"] != ""
        assert isinstance(fellow["posting_id"], str)

    def test_empty_html_returns_empty(self) -> None:
        assert parse_jsonld_jobs("test", "Test", "") == []

    def test_no_intern_postings_returns_empty(self) -> None:
        html = """
        <script type="application/ld+json">
        {"@type": "JobPosting", "title": "VP of Engineering", "url": "https://x.com/1"}
        </script>
        """
        assert parse_jsonld_jobs("test", "Test", html) == []


class TestWorkdayCompanies:
    """Validate the WORKDAY_COMPANIES config."""

    def test_all_companies_have_required_keys(self) -> None:
        for company in WORKDAY_COMPANIES:
            assert "slug" in company
            assert "host" in company
            assert "path" in company
            assert "name" in company

    def test_slugs_are_unique(self) -> None:
        slugs = [c["slug"] for c in WORKDAY_COMPANIES]
        assert len(slugs) == len(set(slugs))
