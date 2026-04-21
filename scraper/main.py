"""Main entry point for jojo-scraper: scheduler + feed server."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import re

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import POLL_INTERVAL_MINUTES, get_direct_source_alert_policy, is_direct_source_alerting_enabled
from db import PostingDB
from discord_alert import send_alert, send_uiuc_alert, send_uiuc_constant_template_alert
from feed import start_feed_server
from matching import classify_posting
from runtime_env import load_project_env
from sources import amazon, apple, ashby, greenhouse, lever, netflix, smartrecruiters, uiuc, workday, workday_api
from uiuc_alumni import (
    build_alumni_patterns,
    build_source_records_from_alumni_patterns,
    load_alumni_profile_records,
    normalize_linkedin_profile_record,
)
from uiuc_alumni_collector import get_last_collector_summary, run_alumni_collector
from uiuc_config import UIUC_MAX_PINGS_PER_RUN
from uiuc_outputs import sync_uiuc_outputs, write_outreach_backfill
from uiuc_outreach import enrich_outreach_opportunities, get_email_constant_paragraph
from uiuc_scout import build_opportunities, select_ping_candidates

try:
    from sources import google
except ImportError:
    google = None

try:
    from sources import talentbrew
except ImportError:
    talentbrew = None

try:
    from sources import airbnb
except ImportError:
    airbnb = None


load_project_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("jojo")

db = PostingDB(os.environ.get("DB_PATH", "postings.db"))


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _resolve_uiuc_output_dir() -> Path:
    env_dir = os.environ.get("UIUC_SCOUT_OUTPUT_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    return Path.home() / "Vault" / "NanoClaw" / "uiuc-scout"


def _attach_outreach_doc_paths(opportunities: list[dict]) -> list[dict]:
    output_dir = _resolve_uiuc_output_dir()
    enriched: list[dict] = []
    for opportunity in opportunities:
        if opportunity.get("type") != "cold_outreach_target":
            enriched.append(dict(opportunity))
            continue

        slug = _slugify(str(opportunity.get("title", opportunity.get("id", "outreach"))))
        enriched.append(
            {
                **opportunity,
                "lab_doc_path": str(opportunity.get("lab_doc_path", output_dir / "labs" / f"{slug}.md")),
                "outreach_doc_path": str(
                    opportunity.get(
                        "outreach_doc_path",
                        output_dir / "outreach" / f"{slug}.md",
                    )
                ),
            }
        )
    return enriched


def _extract_markdown_section(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"## {re.escape(heading)}\n\n(.*?)(?=\n## |\Z)",
        re.DOTALL,
    )
    match = pattern.search(markdown)
    return match.group(1).strip() if match else ""


def _extract_markdown_line(markdown: str, prefix: str) -> str:
    for line in markdown.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):].strip().strip("`")
    return ""


def _parse_saved_outreach_doc(path: Path) -> dict | None:
    try:
        markdown = path.read_text(encoding="utf-8")
    except OSError:
        return None

    title = _extract_markdown_line(markdown, "# ")
    opportunity_type = _extract_markdown_line(markdown, "- Type: ")
    if opportunity_type != "cold_outreach_target":
        return None

    link_section = _extract_markdown_section(markdown, "Link")
    url = next((line.strip() for line in link_section.splitlines() if line.strip()), "")
    if not title or not url:
        return None

    reasons = [
        line[2:].strip()
        for line in _extract_markdown_section(markdown, "Why It Matches").splitlines()
        if line.startswith("- ")
    ]
    mirrors = [
        line[2:].strip()
        for line in _extract_markdown_section(markdown, "Mirrors").splitlines()
        if line.startswith("- ")
    ]
    alumni_patterns = [
        line[2:].strip()
        for line in _extract_markdown_section(markdown, "Alumni Signals").splitlines()
        if line.startswith("- ")
    ]
    skills_line = _extract_markdown_line(markdown, "- Skills: ")
    tags_line = _extract_markdown_line(markdown, "- Tags: ")
    evidence_line = _extract_markdown_line(markdown, "- Evidence sources: ")
    evidence_sources = (
        ["official"]
        if evidence_line == "official"
        else [item.strip() for item in evidence_line.split(",") if item.strip()]
    )

    return {
        "id": path.stem,
        "source": "vault_backfill",
        "title": title,
        "url": url,
        "type": opportunity_type,
        "track": _extract_markdown_line(markdown, "- Track: "),
        "total_score": float(_extract_markdown_line(markdown, "- Score: ") or 0),
        "next_action": _extract_markdown_line(markdown, "- Next action: ") or "reach_out",
        "status": _extract_markdown_line(markdown, "- Status: ") or "rolling",
        "fit_reasons": reasons,
        "company_archetypes": mirrors,
        "skills": [] if skills_line in {"", "None captured"} else [item.strip() for item in skills_line.split(",") if item.strip()],
        "tags": [] if tags_line in {"", "None captured"} else [item.strip() for item in tags_line.split(",") if item.strip()],
        "evidence_sources": evidence_sources,
        "alumni_patterns": alumni_patterns,
        "alumni_evidence_count": int(_extract_markdown_line(markdown, "- Alumni evidence count: ") or 0),
        "outreach_doc_path": str(path),
    }


def _load_saved_outreach_docs(output_dir: Path) -> list[dict]:
    outreach_dir = output_dir / "outreach"
    if not outreach_dir.exists():
        return []

    opportunities: list[dict] = []
    for path in sorted(outreach_dir.glob("*.md")):
        opportunity = _parse_saved_outreach_doc(path)
        if opportunity is None:
            continue
        opportunities.append(opportunity)
    return opportunities


async def process_postings(
    postings: list[dict],
    source: str,
) -> None:
    """Check each posting against DB, classify, store, and alert."""
    new_count = 0
    for posting in postings:
        posting_id = str(posting.get("posting_id", "")).strip()
        company_slug = str(posting.get("company_slug", "unknown")).strip()
        if not posting_id or not db.is_new(source, company_slug, posting_id):
            continue

        match = classify_posting(posting.get("title", ""), posting.get("description", ""))
        if match is None:
            continue

        posting["track"] = match["track"]
        db.mark_seen(
            source=source,
            company_slug=company_slug,
            posting_id=posting_id,
            title=posting.get("title", ""),
            url=posting.get("url", ""),
            track=match["track"],
            company_name=posting.get("company_name", ""),
            skills=posting.get("skills", ""),
            comp=posting.get("comp", ""),
            team=posting.get("team", ""),
            deadline=posting.get("deadline", ""),
        )

        if is_direct_source_alerting_enabled(company_slug):
            try:
                await send_alert(posting)
            except Exception as e:
                logger.error("Failed to send alert: %s", e)
        else:
            policy = get_direct_source_alert_policy(company_slug)
            logger.info(
                "[%s] tracked posting stored without alert for %s because alerting is disabled (%s)",
                source,
                company_slug,
                policy.get("reason", "no reason recorded"),
            )

        new_count += 1

    if new_count > 0:
        logger.info("[%s] %d new postings found and alerted", source, new_count)


async def process_uiuc_records(
    records: list[dict],
    alumni_profile_records: list[dict] | None = None,
) -> None:
    """Normalize, store, alert, and export UIUC scout opportunities."""
    normalized_profiles = [
        profile
        for profile in (
            normalize_linkedin_profile_record(record)
            for record in (alumni_profile_records or [])
        )
        if profile is not None
    ]
    alumni_patterns = build_alumni_patterns(normalized_profiles)
    derived_records = build_source_records_from_alumni_patterns(alumni_patterns)
    hidden_pathway_records = [
        dict(record)
        for record in records
        if record.get("hidden_pathway_signal")
    ]
    queue_hidden_pathway_records = [
        record
        for record in hidden_pathway_records
        if int(record.get("hidden_pathway_score", 0) or 0) >= 16
    ]
    official_records = [
        dict(record)
        for record in records
        if not record.get("hidden_pathway_signal")
    ]
    opportunities = build_opportunities(
        [*official_records, *queue_hidden_pathway_records, *derived_records],
        alumni_patterns=alumni_patterns,
        hidden_pathway_records=hidden_pathway_records,
    )
    opportunities = await enrich_outreach_opportunities(opportunities)
    opportunities = _attach_outreach_doc_paths(opportunities)
    new_count = 0
    new_opportunities: list[dict] = []

    for opportunity in opportunities:
        source = str(opportunity.get("source", "uiuc_scout"))
        opportunity_id = str(opportunity.get("id", ""))
        if not opportunity_id or not db.is_new_uiuc(source, opportunity_id):
            continue

        db.mark_uiuc_seen(source, opportunity)
        new_opportunities.append(opportunity)
        new_count += 1

    db.refresh_uiuc_snapshot(opportunities)

    for opportunity in select_ping_candidates(new_opportunities, UIUC_MAX_PINGS_PER_RUN):
        try:
            await send_uiuc_alert(opportunity)
        except Exception as exc:
            logger.error("Failed to send UIUC scout alert: %s", exc)

    try:
        sync_uiuc_outputs(
            opportunities,
            alumni_patterns=alumni_patterns,
            alumni_profiles=normalized_profiles,
            source_health=uiuc.get_last_source_health(),
            collector_summary=get_last_collector_summary(),
            hidden_pathway_records=hidden_pathway_records,
        )
    except Exception as exc:
        logger.error("Failed to sync UIUC scout outputs: %s", exc)

    if new_count > 0:
        logger.info("[uiuc_scout] %d new opportunities found", new_count)


async def resend_uiuc_outreach_with_drafts() -> int:
    """Backfill outreach docs and resend current cold-outreach targets with email drafts."""
    current_snapshot = db.get_all_uiuc()
    using_vault_fallback = False
    if not current_snapshot:
        current_snapshot = _load_saved_outreach_docs(_resolve_uiuc_output_dir())
        using_vault_fallback = True
    if not current_snapshot:
        return 0

    enriched_snapshot = await enrich_outreach_opportunities(current_snapshot)
    enriched_snapshot = _attach_outreach_doc_paths(enriched_snapshot)

    try:
        write_outreach_backfill(enriched_snapshot)
    except Exception as exc:
        logger.error("Failed to sync UIUC outreach backfill outputs: %s", exc)

    await send_uiuc_constant_template_alert(get_email_constant_paragraph())

    targets = [
        opportunity
        for opportunity in enriched_snapshot
        if opportunity.get("type") == "cold_outreach_target"
        and opportunity.get("next_action") == "reach_out"
    ]
    targets.sort(
        key=lambda opportunity: (
            opportunity.get("email_quality") != "send_ready",
            -float(opportunity.get("total_score", 0) or 0),
            str(opportunity.get("title", "")),
        )
    )
    for opportunity in targets:
        try:
            await send_uiuc_alert(opportunity)
        except Exception as exc:
            logger.error("Failed to resend UIUC outreach alert: %s", exc)
        await asyncio.sleep(0.35)

    logger.info("[uiuc_outreach_resend] resent %d cold-outreach alerts", len(targets))
    return len(targets)


# ── Poll functions for each source ────────────────────────────────────


async def poll_greenhouse() -> None:
    postings = await greenhouse.poll_all()
    await process_postings(postings, "greenhouse")


async def poll_ashby() -> None:
    postings = await ashby.poll_all()
    await process_postings(postings, "ashby")


async def poll_lever() -> None:
    postings = await lever.poll_all()
    await process_postings(postings, "lever")


async def poll_amazon_jobs() -> None:
    postings = await amazon.poll_all()
    await process_postings(postings, "amazon")


async def poll_google_jobs() -> None:
    if google is None:
        return
    postings = await google.poll_all()
    await process_postings(postings, "google")


async def poll_talentbrew_jobs() -> None:
    if talentbrew is None:
        return
    postings = await talentbrew.poll_all()
    await process_postings(postings, "talentbrew")


async def poll_airbnb_jobs() -> None:
    if airbnb is None:
        return
    postings = await airbnb.poll_all()
    await process_postings(postings, "airbnb")


async def poll_apple_jobs() -> None:
    postings = await apple.poll_all()
    await process_postings(postings, "apple")


async def poll_workday_feeds() -> None:
    postings = await workday.poll_all()
    await process_postings(postings, "workday")


async def poll_smartrecruiters_jobs() -> None:
    postings = await smartrecruiters.poll_all()
    await process_postings(postings, "smartrecruiters")


async def poll_netflix_jobs() -> None:
    postings = await netflix.poll_all()
    await process_postings(postings, "netflix")


async def poll_workday_api_jobs() -> None:
    postings = await workday_api.poll_all()
    await process_postings(postings, "workday_api")


async def poll_uiuc_scout() -> None:
    records = await uiuc.poll_all()
    alumni_profile_records = load_alumni_profile_records()
    await process_uiuc_records(records, alumni_profile_records)


async def poll_uiuc_alumni_collector() -> None:
    summary = await run_alumni_collector(mode="hybrid")
    logger.info(
        "[uiuc_alumni_collector] queries=%s candidates=%s promoted=%s",
        summary.get("queries_run", 0),
        summary.get("candidates_found", 0),
        summary.get("profiles_promoted", 0),
    )


async def poll_uiuc_full_pipeline() -> None:
    try:
        await poll_uiuc_alumni_collector()
    except Exception as exc:
        logger.error("UIUC alumni collector failed; continuing with official scout: %s", exc)
    await poll_uiuc_scout()


async def _async_main() -> None:
    logger.info("Starting jojo-scraper")

    start_feed_server(db)
    logger.info("Feed server started on port 8080")

    scheduler = AsyncIOScheduler()

    # Tier 1: Direct APIs - every 15 min
    scheduler.add_job(
        poll_greenhouse,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["greenhouse"],
        id="greenhouse",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_ashby,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["ashby"],
        id="ashby",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_lever,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["lever"],
        id="lever",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_google_jobs,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["google"],
        id="google",
        next_run_time=None,
    ) if google is not None else None
    scheduler.add_job(
        poll_talentbrew_jobs,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["talentbrew"],
        id="talentbrew",
        next_run_time=None,
    ) if talentbrew is not None else None
    scheduler.add_job(
        poll_airbnb_jobs,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["airbnb"],
        id="airbnb",
        next_run_time=None,
    ) if airbnb is not None else None
    scheduler.add_job(
        poll_amazon_jobs,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["amazon"],
        id="amazon",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_apple_jobs,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["apple"],
        id="apple",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_workday_feeds,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["workday"],
        id="workday",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_smartrecruiters_jobs,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["smartrecruiters"],
        id="smartrecruiters",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_netflix_jobs,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["netflix"],
        id="netflix",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_workday_api_jobs,
        "interval",
        minutes=POLL_INTERVAL_MINUTES["workday_api"],
        id="workday_api",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_uiuc_full_pipeline,
        "interval",
        minutes=1440,
        id="uiuc_alumni_collector",
        next_run_time=None,
    )
    scheduler.add_job(
        poll_uiuc_scout,
        "interval",
        minutes=240,
        id="uiuc_scout",
        next_run_time=None,
    )

    scheduler.start()
    logger.info("Scheduler started -- direct careers sources armed")

    # Run initial poll — individual failures are logged, not raised
    initial_tasks = [
        poll_greenhouse(),
        poll_ashby(),
        poll_lever(),
        poll_amazon_jobs(),
        poll_apple_jobs(),
        poll_workday_feeds(),
        poll_smartrecruiters_jobs(),
        poll_netflix_jobs(),
        poll_workday_api_jobs(),
        poll_uiuc_full_pipeline(),
    ]
    if google is not None:
        initial_tasks.append(poll_google_jobs())
    if talentbrew is not None:
        initial_tasks.append(poll_talentbrew_jobs())
    if airbnb is not None:
        initial_tasks.append(poll_airbnb_jobs())

    results = await asyncio.gather(
        *initial_tasks,
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            logger.error("Initial poll error: %s", r)
    logger.info("Initial poll complete")

    # Keep running until interrupted
    await asyncio.Event().wait()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
