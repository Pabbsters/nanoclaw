"""Tests for discord_alert module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from config import TRACK_EMOJI
from discord_alert import (
    _resolve_uiuc_discord_channel_id,
    format_alert,
    format_uiuc_alert,
    send_alert,
    send_uiuc_alert,
)


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


class TestFormatUiucAlert:
    """UIUC scout alerts should be concise and action-oriented."""

    def test_formats_uiuc_opportunity(self) -> None:
        opportunity = {
            "title": "Bo Li - Trustworthy AI",
            "type": "cold_outreach_target",
            "track": "ml_ai_research",
            "org": "UIUC",
            "department": "CS",
            "total_score": 81,
            "next_action": "reach_out",
            "fit_reasons": ["Trustworthy AI fit", "AI research experience"],
            "evidence_sources": ["official", "alumni"],
            "alumni_patterns": ["Bo Li Lab"],
            "company_archetypes": ["Anthropic"],
            "url": "https://example.com/bo-li",
        }

        result = format_uiuc_alert(opportunity)

        assert result.startswith("🎓 **UIUC Scout:")
        assert "Type: cold_outreach_target" in result
        assert "Score: 81" in result
        assert "Next: reach_out" in result
        assert "Evidence: official, alumni" in result
        assert "Alumni signals: Bo Li Lab" in result
        assert "Mirrors: Anthropic" in result
        assert "Why: Trustworthy AI fit" in result


class TestResolveUiucDiscordChannelId:
    """UIUC scout can infer a DM channel from the local nanoclaw store."""

    def test_reads_first_discord_dm_from_messages_db(self, tmp_path: Path) -> None:
        import sqlite3

        db_path = tmp_path / "messages.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TEXT, channel TEXT, is_group INTEGER DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO chats (jid, name, channel, is_group) VALUES (?, ?, ?, ?)",
            ("dc:1234567890", "Pabbsters", "discord", 0),
        )
        conn.commit()
        conn.close()

        channel_id = _resolve_uiuc_discord_channel_id(str(db_path))

        assert channel_id == "1234567890"


class TestSendUiucAlertFallback:
    """When no webhook is configured, the bot-token fallback should still work."""

    @pytest.mark.asyncio
    async def test_uses_bot_token_fallback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import sqlite3

        db_path = tmp_path / "messages.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TEXT, channel TEXT, is_group INTEGER DEFAULT 0)"
        )
        conn.execute(
            "INSERT INTO chats (jid, name, channel, is_group) VALUES (?, ?, ?, ?)",
            ("dc:1234567890", "Pabbsters", "discord", 0),
        )
        conn.commit()
        conn.close()

        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-bot-token")
        monkeypatch.setenv("NANOCLAW_MESSAGES_DB", str(db_path))

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("discord_alert.httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await send_uiuc_alert(
                {
                    "title": "Victor Duarte - Quantitative Finance and Machine Learning",
                    "type": "cold_outreach_target",
                    "track": "quant_fintech",
                    "org": "UIUC",
                    "total_score": 104,
                    "next_action": "reach_out",
                    "fit_reasons": ["Quant fit"],
                    "url": "https://experts.illinois.edu/en/persons/victor-duarte/",
                }
            )

        assert mock_post.await_count == 1
        called_url = mock_post.await_args.args[0]
        called_headers = mock_post.await_args.kwargs["headers"]
        assert called_url == "https://discord.com/api/v10/channels/1234567890/messages"
        assert called_headers["Authorization"] == "Bot test-bot-token"


class TestSendAlertWebhook:
    """Webhook sends should read the current env value at send-time."""

    @pytest.mark.asyncio
    async def test_send_alert_uses_webhook_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("discord_alert.httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await send_alert(
                {
                    "title": "ML Engineer Intern",
                    "company_name": "Anthropic",
                    "url": "https://example.com/job/42",
                    "track": "ai_data",
                }
            )

        assert mock_post.await_count == 1
        assert mock_post.await_args.args[0] == "https://discord.example/webhook"

    @pytest.mark.asyncio
    async def test_send_uiuc_alert_prefers_webhook_when_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-bot-token")
        monkeypatch.setenv("UIUC_SCOUT_DISCORD_CHANNEL_ID", "1234567890")

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None

        with patch("discord_alert.httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)) as mock_post:
            await send_uiuc_alert(
                {
                    "title": "Victor Duarte - Quantitative Finance and Machine Learning",
                    "type": "cold_outreach_target",
                    "track": "quant_fintech",
                    "org": "UIUC",
                    "total_score": 104,
                    "next_action": "reach_out",
                    "fit_reasons": ["Quant fit"],
                    "url": "https://experts.illinois.edu/en/persons/victor-duarte/",
                }
            )

        assert mock_post.await_count == 1
        assert mock_post.await_args.args[0] == "https://discord.example/webhook"
