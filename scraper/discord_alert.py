"""Discord webhook alert formatter and sender."""

from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path

import httpx

from config import TRACK_EMOJI
from runtime_env import load_project_env

load_project_env()

def _get_webhook_url() -> str:
    load_project_env()
    return os.environ.get("DISCORD_WEBHOOK_URL", "").strip()


def format_alert(posting: dict) -> str:
    """Format a posting dict into a Discord message string.

    Required keys: title, company_name, url, track
    Optional keys: team, skills, deadline, comp

    Uses Format B with track emoji prefix.
    """
    emoji = TRACK_EMOJI.get(posting.get("track", ""), "\u26aa")
    header = f"{emoji} **NEW: {posting['title']} @ {posting['company_name']}**"

    lines: list[str] = [header]

    if posting.get("team"):
        lines.append(f"Team: {posting['team']}")
    if posting.get("skills"):
        lines.append(f"Skills: {posting['skills']}")
    if posting.get("deadline"):
        lines.append(f"Deadline: {posting['deadline']}")
    if posting.get("comp"):
        lines.append(f"Comp: {posting['comp']}")

    lines.append(f"Link: {posting['url']}")

    slug = posting.get("company_name", "unknown").lower().replace(" ", "-")
    lines.append(f"\U0001f4c4 Prep doc \u2192 Vault/companies/{slug}.md")

    return "\n".join(lines)


def format_uiuc_alert(opportunity: dict) -> str:
    """Format a UIUC scout opportunity into a Discord message string."""
    lines = [
        f"\U0001f393 **UIUC Scout: {opportunity['title']}**",
        f"Type: {opportunity.get('type', 'unknown')}",
        f"Track: {opportunity.get('track', 'unknown')}",
        f"Score: {opportunity.get('total_score', 0)}",
        f"Next: {opportunity.get('next_action', 'track')}",
    ]

    org = opportunity.get("org") or opportunity.get("department")
    if org:
        lines.append(f"Org: {org}")
    if opportunity.get("evidence_sources"):
        lines.append(f"Evidence: {', '.join(opportunity.get('evidence_sources', []))}")
    if opportunity.get("alumni_patterns"):
        lines.append(f"Alumni signals: {', '.join(opportunity.get('alumni_patterns', [])[:2])}")
    if opportunity.get("company_archetypes"):
        lines.append(f"Mirrors: {', '.join(opportunity.get('company_archetypes', [])[:3])}")
    if opportunity.get("fit_reasons"):
        lines.append(f"Why: {opportunity['fit_reasons'][0]}")
    if opportunity.get("type") == "cold_outreach_target":
        if opportunity.get("email_quality"):
            lines.append(f"Email quality: {opportunity['email_quality']}")
        if opportunity.get("email_intro"):
            lines.extend(["", f"Email intro: {opportunity['email_intro']}"])
        if opportunity.get("email_observation_paragraph"):
            lines.append(f"Email opener: {opportunity['email_observation_paragraph']}")
        if opportunity.get("email_hook_source"):
            lines.append(f"Hook source: {opportunity['email_hook_source']}")
        if opportunity.get("email_skill_alignment"):
            lines.append(f"Skills to mention: {', '.join(opportunity.get('email_skill_alignment', []))}")
        if opportunity.get("email_review_reason"):
            lines.append(f"Review before sending: {opportunity['email_review_reason']}")
        if opportunity.get("outreach_doc_path"):
            lines.append(f"Full draft: {opportunity['outreach_doc_path']}")
    lines.append(f"Link: {opportunity['url']}")
    return "\n".join(lines)


def format_uiuc_constant_template_alert(message: str) -> str:
    return "\n".join(
        [
            "\U0001f4cc **UIUC Scout Outreach Constant Paragraph**",
            "Pin this once and reuse it as the second paragraph for cold outreach.",
            "",
            message.strip(),
        ]
    )


async def send_alert(posting: dict) -> None:
    """Send a single alert via Discord webhook. Skip if WEBHOOK_URL not set."""
    webhook_url = _get_webhook_url()
    if not webhook_url:
        return

    message = format_alert(posting)
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(webhook_url, json={"content": message})
        response.raise_for_status()


async def send_batch_alerts(postings: list[dict]) -> None:
    """Send multiple alerts sequentially."""
    for posting in postings:
        await send_alert(posting)


async def send_uiuc_alert(opportunity: dict) -> None:
    message = format_uiuc_alert(opportunity)
    await _send_uiuc_message(message)


async def send_uiuc_constant_template_alert(message: str) -> None:
    await _send_uiuc_message(format_uiuc_constant_template_alert(message))


async def _send_uiuc_message(message: str) -> None:
    webhook_url = _get_webhook_url()
    if webhook_url:
        async with httpx.AsyncClient(timeout=15) as client:
            await _post_discord_message(client, webhook_url, {"content": message})
        return

    bot_token = os.environ.get("DISCORD_BOT_TOKEN", "")
    channel_id = (
        os.environ.get("UIUC_SCOUT_DISCORD_CHANNEL_ID", "")
        or _resolve_uiuc_discord_channel_id()
    )
    if not bot_token or not channel_id:
        return

    async with httpx.AsyncClient(timeout=15) as client:
        await _post_discord_message(
            client,
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            {"content": message},
            headers={
                "Authorization": f"Bot {bot_token}",
                "Content-Type": "application/json",
            },
        )


async def _post_discord_message(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
    max_attempts: int = 5,
) -> None:
    for attempt in range(max_attempts):
        response = await client.post(url, headers=headers, json=payload)
        status_code = _coerce_status_code(response)
        if status_code != 429:
            response.raise_for_status()
            return

        if attempt == max_attempts - 1:
            response.raise_for_status()
            return

        await asyncio.sleep(_extract_retry_after_seconds(response))


def _coerce_status_code(response: httpx.Response) -> int:
    status_code = getattr(response, "status_code", 200)
    return status_code if isinstance(status_code, int) else 200


def _extract_retry_after_seconds(response: httpx.Response) -> float:
    retry_after_header = getattr(response, "headers", {}).get("Retry-After")
    try:
        if retry_after_header is not None:
            return max(float(retry_after_header), 0.5)
    except (TypeError, ValueError):
        pass

    try:
        payload = response.json()
    except Exception:
        payload = {}

    retry_after = payload.get("retry_after", 1.5) if isinstance(payload, dict) else 1.5
    try:
        return max(float(retry_after), 0.5)
    except (TypeError, ValueError):
        return 1.5


def _resolve_uiuc_discord_channel_id(messages_db_path: str | None = None) -> str:
    """Resolve a Discord DM channel from the local nanoclaw messages DB."""
    db_path = messages_db_path or os.environ.get("NANOCLAW_MESSAGES_DB", "")
    if not db_path:
        candidate = Path.home() / "nanoclaw" / "store" / "messages.db"
        if candidate.exists():
            db_path = str(candidate)

    if not db_path or not Path(db_path).exists():
        return ""

    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT jid FROM chats WHERE channel = 'discord' AND is_group = 0 ORDER BY last_message_time DESC LIMIT 1"
        ).fetchone()
    except sqlite3.Error:
        return ""
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not row or not row[0].startswith("dc:"):
        return ""
    return row[0][3:]
