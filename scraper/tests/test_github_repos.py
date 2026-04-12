"""Tests for sources/github_repos module."""

from __future__ import annotations

import pytest

from sources.github_repos import parse_readme_table, _posting_id, _slug_from_name


# ── Mock data matching SimplifyJobs README format ─────────────────────

MOCK_README = """\
# Summer 2026 Tech Internships

| Company | Role | Location | Application/Link | Date Posted |
| --- | --- | --- | --- | --- |
| **Google** | Software Engineering Intern | Mountain View, CA | [Apply](https://careers.google.com/jobs/123) | Jan 15 |
| **Meta** | ML Research Intern | Menlo Park, CA | [Apply](https://metacareers.com/jobs/456) | Jan 14 |
| Amazon | Data Engineer Intern | Seattle, WA | [Apply](https://amazon.jobs/en/jobs/789) | Jan 13 |
| **Jane Street** | Quantitative Trader Intern | New York, NY | [Apply](https://janestreet.com/apply/012) | Jan 12 |
"""

MOCK_README_NO_LINKS = """\
| Company | Role | Location | Application/Link | Date Posted |
| --- | --- | --- | --- | --- |
| Google | SWE Intern | NYC | N/A | Jan 10 |
"""

MOCK_README_EMPTY = """\
# No listings yet

Check back later.
"""


class TestParseReadmeTable:
    """Test markdown table parsing."""

    def test_parses_all_rows(self) -> None:
        results = parse_readme_table(MOCK_README)
        assert len(results) == 4

    def test_correct_field_mapping(self) -> None:
        results = parse_readme_table(MOCK_README)
        google = results[0]
        assert google["title"] == "Software Engineering Intern"
        assert google["url"] == "https://careers.google.com/jobs/123"
        assert google["company_name"] == "Google"
        assert google["company_slug"] == "google"
        assert google["location"] == "Mountain View, CA"
        assert google["team"] == ""
        assert google["skills"] == ""

    def test_strips_bold_markdown(self) -> None:
        results = parse_readme_table(MOCK_README)
        assert results[0]["company_name"] == "Google"
        assert results[1]["company_name"] == "Meta"

    def test_extracts_urls(self) -> None:
        results = parse_readme_table(MOCK_README)
        urls = [r["url"] for r in results]
        assert "https://careers.google.com/jobs/123" in urls
        assert "https://metacareers.com/jobs/456" in urls

    def test_skips_rows_without_links(self) -> None:
        results = parse_readme_table(MOCK_README_NO_LINKS)
        assert len(results) == 0

    def test_empty_readme(self) -> None:
        results = parse_readme_table(MOCK_README_EMPTY)
        assert results == []

    def test_posting_id_is_deterministic(self) -> None:
        results = parse_readme_table(MOCK_README)
        ids = [r["posting_id"] for r in results]
        # Re-parse should give same IDs
        results2 = parse_readme_table(MOCK_README)
        ids2 = [r["posting_id"] for r in results2]
        assert ids == ids2

    def test_posting_id_is_string(self) -> None:
        results = parse_readme_table(MOCK_README)
        for r in results:
            assert isinstance(r["posting_id"], str)
            assert len(r["posting_id"]) == 16


class TestHelpers:
    """Test helper functions."""

    def test_posting_id_deterministic(self) -> None:
        assert _posting_id("https://example.com") == _posting_id("https://example.com")

    def test_posting_id_different_urls(self) -> None:
        assert _posting_id("https://a.com") != _posting_id("https://b.com")

    def test_slug_from_name(self) -> None:
        assert _slug_from_name("Google") == "google"
        assert _slug_from_name("Jane Street") == "jane-street"
        assert _slug_from_name("D.E. Shaw") == "d-e-shaw"
        assert _slug_from_name("  Spaces  ") == "spaces"
