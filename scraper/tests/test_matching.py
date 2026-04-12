"""Tests for the matching / classification engine."""

from __future__ import annotations

import pytest

from matching import classify_posting


# ── Basic classification ───────────────────────────────────────────────

class TestClassifyPosting:
    """classify_posting returns the highest-priority track that matches."""

    def test_ai_data_title_match(self):
        result = classify_posting("ML Engineer Intern - Summer 2026")
        assert result is not None
        assert result["track"] == "ai_data"
        assert result["priority"] == 0

    def test_swe_title_match(self):
        result = classify_posting("Software Engineer - Backend")
        assert result is not None
        assert result["track"] == "swe"

    def test_sales_technical_match(self):
        result = classify_posting("Solutions Architect - Enterprise")
        assert result is not None
        assert result["track"] == "sales_technical"

    def test_consulting_match(self):
        result = classify_posting("Technology Consultant - New Grad")
        assert result is not None
        assert result["track"] == "consulting"

    def test_extras_match(self):
        result = classify_posting("Quantitative Developer - Trading")
        assert result is not None
        assert result["track"] == "extras"

    def test_cloud_infra_match(self):
        result = classify_posting("Site Reliability Engineer")
        assert result is not None
        assert result["track"] == "cloud_infra"

    def test_no_match_returns_none(self):
        result = classify_posting("Office Manager - HR Department")
        assert result is None

    def test_empty_title_returns_none(self):
        result = classify_posting("")
        assert result is None


# ── Priority ordering ──────────────────────────────────────────────────

class TestPriorityOrdering:
    """When multiple tracks could match, highest priority wins."""

    def test_ai_data_beats_swe(self):
        # "data engineer" is ai_data (priority 0), description mentions software
        result = classify_posting(
            "Data Engineer",
            description="software engineer background preferred",
        )
        assert result is not None
        assert result["track"] == "ai_data"
        assert result["priority"] == 0

    def test_priority_value_is_index(self):
        result = classify_posting("DevOps Engineer")
        assert result is not None
        assert result["track"] == "cloud_infra"
        assert result["priority"] == 5


# ── Case insensitivity ────────────────────────────────────────────────

class TestCaseInsensitivity:

    def test_uppercase_title(self):
        result = classify_posting("MACHINE LEARNING ENGINEER")
        assert result is not None
        assert result["track"] == "ai_data"

    def test_mixed_case_title(self):
        result = classify_posting("Software ENGINEER Intern")
        assert result is not None
        assert result["track"] == "swe"


# ── Description matching ──────────────────────────────────────────────

class TestDescriptionMatching:

    def test_keyword_in_description_only(self):
        result = classify_posting(
            "Junior Role - Open Position",
            description="Looking for a data scientist with Python experience",
        )
        assert result is not None
        assert result["track"] == "ai_data"

    def test_description_default_empty(self):
        result = classify_posting("Random Job Title")
        assert result is None


# ── Word boundary matching ────────────────────────────────────────────

class TestWordBoundary:

    def test_partial_word_does_not_match(self):
        # "consulting" should match, but "insult" should not match "consultant"
        result = classify_posting("Insultingly Bad Job Title")
        assert result is None

    def test_sre_matches_as_whole_word(self):
        result = classify_posting("SRE - Production Systems")
        assert result is not None
        assert result["track"] == "cloud_infra"

    def test_sre_inside_word_no_match(self):
        # "sre" embedded in another word should not match
        result = classify_posting("Measureless Ocean Explorer")
        assert result is None


# ── Matched keyword returned ──────────────────────────────────────────

class TestMatchedKeyword:

    def test_returns_matched_keyword(self):
        result = classify_posting("Senior ML Engineer - NLP Team")
        assert result is not None
        assert result["matched_keyword"] == "ml engineer"

    def test_returns_first_matching_keyword_for_track(self):
        result = classify_posting("Deep Learning Research Scientist")
        assert result is not None
        assert result["track"] == "ai_data"
        # Should match one of the ai_data keywords
        assert result["matched_keyword"] in [
            "deep learning", "research scientist",
        ]
