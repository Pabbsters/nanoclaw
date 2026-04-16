"""Main entry point for jojo-scraper: scheduler + feed server."""

from __future__ import annotations

import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import PostingDB
from discord_alert import send_alert, send_uiuc_alert
from feed import start_feed_server
from matching import classify_posting
from runtime_env import load_project_env
from sources import (
    amazon,
    apple,
    ashby,
    github_repos,
    greenhouse,
    hn,
    jobspy_agg,
    lever,
    netflix,
    reddit,
    smartrecruiters,
    uiuc,
    workday,
)
from uiuc_alumni import (
    build_alumni_patterns,
    build_source_records_from_alumni_patterns,
    load_alumni_profile_records,
    normalize_linkedin_profile_record,
)
from uiuc_alumni_collector import get_last_collector_summary, run_alumni_collector
from uiuc_config import UIUC_MAX_PINGS_PER_RUN
from uiuc_outputs import sync_uiuc_outputs
from uiuc_scout import build_opportunities, select_ping_candidates


load_project_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("jojo")

db = PostingDB(os.environ.get("DB_PATH", "postings.db"))


async def process_postings(postings: list[dict], source: str) -> None:
    """Check each posting against DB, classify, store, and alert."""
    new_count = 0
    for posting in postings:
        posting_id = str(posting.get("posting_id", ""))
        company_slug = str(posting.get("company_slug", "unknown"))
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

        try:
            await send_alert(posting)
        except Exception as exc:
            logger.error("Failed to send alert: %s", exc)

        new_count += 1

    if new_count > 0:
        logger.info("[%s] %d new postings found and alerted", source, new_count)


async def process_uiuc_records(records: list[dict], alumni_profile_records: list[dict] | None = None) -> None:
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
    opportunities = build_opportunities([*records, *derived_records], alumni_patterns=alumni_patterns)
    new_count = 0
    new_opportunities: list[dict] = []

    for opportunity in opportunities:
        source = opportunity.get("source", "uiuc_scout")
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
        )
    except Exception as exc:
        logger.error("Failed to sync UIUC scout outputs: %s", exc)

    if new_count > 0:
        logger.info("[uiuc_scout] %d new opportunities found", new_count)


async def poll_greenhouse() -> None:
    postings = await greenhouse.poll_all()
    await process_postings(postings, "greenhouse")


async def poll_ashby() -> None:
    postings = await ashby.poll_all()
    await process_postings(postings, "ashby")


async def poll_lever() -> None:
    postings = await lever.poll_all()
    await process_postings(postings, "lever")


async def poll_github() -> None:
    postings = await github_repos.poll_all()
    await process_postings(postings, "github")


async def poll_jobspy_wrapper() -> None:
    """JobSpy is sync, so run it in an executor."""
    loop = asyncio.get_running_loop()
    postings = await loop.run_in_executor(None, jobspy_agg.poll_jobspy)
    await process_postings(postings, "jobspy")


async def poll_amazon_jobs() -> None:
    postings = await amazon.poll_all()
    await process_postings(postings, "amazon")


async def poll_apple_jobs() -> None:
    postings = await apple.poll_all()
    await process_postings(postings, "apple")


async def poll_reddit_feeds() -> None:
    postings = await reddit.poll_all()
    await process_postings(postings, "reddit")


async def poll_hn_feeds() -> None:
    postings = await hn.poll_all()
    await process_postings(postings, "hn")


async def poll_workday_feeds() -> None:
    postings = await workday.poll_all()
    await process_postings(postings, "workday")


async def poll_smartrecruiters() -> None:
    postings = await smartrecruiters.poll_all()
    await process_postings(postings, "smartrecruiters")


async def poll_netflix() -> None:
    postings = await netflix.poll_all()
    await process_postings(postings, "netflix")


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

    scheduler.add_job(poll_greenhouse, "interval", minutes=15, id="greenhouse", next_run_time=None)
    scheduler.add_job(poll_ashby, "interval", minutes=15, id="ashby", next_run_time=None)
    scheduler.add_job(poll_lever, "interval", minutes=15, id="lever", next_run_time=None)
    scheduler.add_job(poll_github, "interval", minutes=15, id="github", next_run_time=None)

    scheduler.add_job(poll_jobspy_wrapper, "interval", minutes=30, id="jobspy", next_run_time=None)
    scheduler.add_job(poll_amazon_jobs, "interval", minutes=30, id="amazon", next_run_time=None)
    scheduler.add_job(poll_apple_jobs, "interval", minutes=30, id="apple", next_run_time=None)
    scheduler.add_job(poll_smartrecruiters, "interval", minutes=30, id="smartrecruiters", next_run_time=None)
    scheduler.add_job(poll_netflix, "interval", minutes=30, id="netflix", next_run_time=None)

    scheduler.add_job(poll_reddit_feeds, "interval", minutes=60, id="reddit", next_run_time=None)
    scheduler.add_job(poll_workday_feeds, "interval", minutes=60, id="workday", next_run_time=None)

    scheduler.add_job(poll_hn_feeds, "interval", minutes=1440, id="hn", next_run_time=None)
    scheduler.add_job(poll_uiuc_full_pipeline, "interval", minutes=1440, id="uiuc_alumni_collector", next_run_time=None)
    scheduler.add_job(poll_uiuc_scout, "interval", minutes=240, id="uiuc_scout", next_run_time=None)

    scheduler.start()
    logger.info("Scheduler started -- all sources armed")

    results = await asyncio.gather(
        poll_greenhouse(),
        poll_ashby(),
        poll_lever(),
        poll_github(),
        poll_jobspy_wrapper(),
        poll_amazon_jobs(),
        poll_apple_jobs(),
        poll_smartrecruiters(),
        poll_netflix(),
        poll_reddit_feeds(),
        poll_hn_feeds(),
        poll_workday_feeds(),
        poll_uiuc_full_pipeline(),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            logger.error("Initial poll error: %s", result)
    logger.info("Initial poll complete")

    await asyncio.Event().wait()


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
