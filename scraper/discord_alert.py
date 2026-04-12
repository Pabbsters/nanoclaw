"""Discord webhook alert formatter and sender."""

from __future__ import annotations

import os

import httpx

from config import TRACK_EMOJI

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


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


async def send_alert(posting: dict) -> None:
    """Send a single alert via Discord webhook. Skip if WEBHOOK_URL not set."""
    if not WEBHOOK_URL:
        return

    message = format_alert(posting)
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(WEBHOOK_URL, json={"content": message})


async def send_batch_alerts(postings: list[dict]) -> None:
    """Send multiple alerts sequentially."""
    for posting in postings:
        await send_alert(posting)
