"""Tests for discord_alert module."""

from __future__ import annotations

import pytest

from config import TRACK_EMOJI
from discord_alert import format_alert


class TestFormatAlertAllTracks:
    """Verify emoji mapping for every track."""

    @pytest.mark.parametrize("track,emoji", list(TRACK_EMOJI.items()))
    def test_correct_emoji_for_track(self, track: str, emoji: str) -> None:
        posting = {
            "title": "ML Intern",
            "company_name": "Acme",
            "url": "https://example.com/job/1",
            "track": track,
        }
        result = format_alert(posting)
        assert result.startswith(f"{emoji} **NEW:")


class TestFormatAlertFullPosting:
    """Test format with all optional fields present."""

    def test_all_fields_present(self) -> None:
        posting = {
            "title": "ML Engineer Intern",
            "company_name": "Anthropic",
            "url": "https://example.com/job/42",
            "track": "ai_data",
            "team": "Research Platform",
            "skills": "Python, PyTorch",
            "deadline": "Rolling",
            "comp": "$65/hr",
        }
        result = format_alert(posting)
        assert "**NEW: ML Engineer Intern @ Anthropic**" in result
        assert "Team: Research Platform" in result
        assert "Skills: Python, PyTorch" in result
        assert "Deadline: Rolling" in result
        assert "Comp: $65/hr" in result
        assert "Link: https://example.com/job/42" in result
        assert "Prep doc" in result
        assert "Vault/companies/anthropic.md" in result


class TestFormatAlertMissingOptionalFields:
    """Omit optional lines when values are missing or empty."""

    def test_no_optional_fields(self) -> None:
        posting = {
            "title": "SWE Intern",
            "company_name": "BigCo",
            "url": "https://example.com/job/99",
            "track": "swe",
        }
        result = format_alert(posting)
        assert "Team:" not in result
        assert "Skills:" not in result
        assert "Deadline:" not in result
        assert "Comp:" not in result
        assert "Link: https://example.com/job/99" in result

    def test_empty_string_optional_fields(self) -> None:
        posting = {
            "title": "Intern",
            "company_name": "Co",
            "url": "https://x.com",
            "track": "extras",
            "team": "",
            "skills": "",
            "deadline": "",
            "comp": "",
        }
        result = format_alert(posting)
        assert "Team:" not in result
        assert "Skills:" not in result

    def test_partial_optional_fields(self) -> None:
        posting = {
            "title": "Cloud Intern",
            "company_name": "AWS",
            "url": "https://aws.com/job/1",
            "track": "cloud_infra",
            "team": "EC2",
            "comp": "$50/hr",
        }
        result = format_alert(posting)
        assert "Team: EC2" in result
        assert "Comp: $50/hr" in result
        assert "Skills:" not in result
        assert "Deadline:" not in result


class TestFormatAlertUnknownTrack:
    """Unknown or missing track falls back to white circle."""

    def test_unknown_track_uses_default_emoji(self) -> None:
        posting = {
            "title": "Intern",
            "company_name": "X",
            "url": "https://x.com",
            "track": "nonexistent_track",
        }
        result = format_alert(posting)
        assert result.startswith("\u26aa **NEW:")

    def test_missing_track_uses_default_emoji(self) -> None:
        posting = {
            "title": "Intern",
            "company_name": "X",
            "url": "https://x.com",
            "track": "",
        }
        result = format_alert(posting)
        assert result.startswith("\u26aa **NEW:")


class TestFormatAlertCompanySlug:
    """Verify prep doc slug generation."""

    def test_multi_word_company_name(self) -> None:
        posting = {
            "title": "Intern",
            "company_name": "Palo Alto Networks",
            "url": "https://x.com",
            "track": "swe",
        }
        result = format_alert(posting)
        assert "Vault/companies/palo-alto-networks.md" in result
