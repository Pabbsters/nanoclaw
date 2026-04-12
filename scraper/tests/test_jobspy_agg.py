"""Tests for sources/jobspy_agg module."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from sources.jobspy_agg import _normalize_row, poll_jobspy


# ── Mock data ─────────────────────────────────────────────────────────

MOCK_ROW: dict = {
    "id": "job-123",
    "title": "Software Engineer Intern",
    "job_url": "https://indeed.com/job/123",
    "company": "Acme Corp",
    "location": "New York, NY",
    "description": "Build amazing things. " * 50,
}

MOCK_ROW_MINIMAL: dict = {
    "title": "Data Intern",
    "job_url": "https://example.com/job/456",
}


class TestNormalizeRow:
    """Test row normalization."""

    def test_full_row(self) -> None:
        result = _normalize_row(MOCK_ROW)
        assert result["posting_id"] == "job-123"
        assert result["title"] == "Software Engineer Intern"
        assert result["url"] == "https://indeed.com/job/123"
        assert result["company_slug"] == "acme-corp"
        assert result["company_name"] == "Acme Corp"
        assert result["location"] == "New York, NY"
        assert result["skills"] == ""
        assert result["team"] == ""

    def test_description_truncated(self) -> None:
        result = _normalize_row(MOCK_ROW)
        assert len(result["description"]) <= 500

    def test_minimal_row(self) -> None:
        result = _normalize_row(MOCK_ROW_MINIMAL)
        assert result["title"] == "Data Intern"
        assert result["url"] == "https://example.com/job/456"
        assert result["company_slug"] == ""
        assert result["company_name"] == ""


class TestPollJobspy:
    """Test poll_jobspy with mocked scrape_jobs."""

    @patch("sources.jobspy_agg.scrape_jobs")
    def test_returns_normalized_results(self, mock_scrape: MagicMock) -> None:
        mock_df = pd.DataFrame([MOCK_ROW])
        mock_scrape.return_value = mock_df

        results = poll_jobspy()
        assert len(results) > 0
        assert results[0]["title"] == "Software Engineer Intern"

    @patch("sources.jobspy_agg.scrape_jobs")
    def test_handles_scrape_exception(self, mock_scrape: MagicMock) -> None:
        mock_scrape.side_effect = Exception("rate limited")
        results = poll_jobspy()
        assert results == []

    @patch("sources.jobspy_agg.scrape_jobs")
    def test_multiple_queries_aggregate(self, mock_scrape: MagicMock) -> None:
        mock_df = pd.DataFrame([MOCK_ROW])
        mock_scrape.return_value = mock_df

        results = poll_jobspy()
        # Called once per query, each returns 1 row
        assert len(results) == mock_scrape.call_count
