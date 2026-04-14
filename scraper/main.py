"""Main entry point for jojo-scraper: scheduler + feed server."""

from __future__ import annotations

import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db import PostingDB
from discord_alert import send_alert
from feed import start_feed_server
from matching import classify_posting
from sources import (
    amazon,
    apple,
    ashby,
    github_repos,
    greenhouse,
    hn,
    jobspy_agg,
    lever,
    reddit,
    workday,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("jojo")

db = PostingDB(os.environ.get("DB_PATH", "postings.db"))


async def process_postings(postings: list[dict], source: str) -> None:
    """Check each posting against DB, classify, store, and alert."""
    new_count = 0
    for p in postings:
        posting_id = str(p.get("posting_id", ""))
        company_slug = p.get("company_slug", "unknown")
        if not posting_id or not db.is_new(source, company_slug, posting_id):
            continue

        match = classify_posting(p.get("title", ""), p.get("description", ""))
        if match is None:
            continue

        p["track"] = match["track"]
        db.mark_seen(
            source=source,
            company_slug=company_slug,
            posting_id=posting_id,
            title=p.get("title", ""),
            url=p.get("url", ""),
            track=match["track"],
            company_name=p.get("company_name", ""),
            skills=p.get("skills", ""),
            comp=p.get("comp", ""),
            team=p.get("team", ""),
            deadline=p.get("deadline", ""),
        )

        try:
            await send_alert(p)
        except Exception as e:
            logger.error("Failed to send alert: %s", e)

        new_count += 1

    if new_count > 0:
        logger.info("[%s] %d new postings found and alerted", source, new_count)


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


async def poll_github() -> None:
    postings = await github_repos.poll_all()
    await process_postings(postings, "github")


async def poll_jobspy_wrapper() -> None:
    """JobSpy is sync - run in executor."""
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


async def _async_main() -> None:
    logger.info("Starting jojo-scraper")

    start_feed_server(db)
    logger.info("Feed server started on port 8080")

    scheduler = AsyncIOScheduler()

    # Tier 1: Direct APIs - every 15 min
    scheduler.add_job(poll_greenhouse, "interval", minutes=15, id="greenhouse", next_run_time=None)
    scheduler.add_job(poll_ashby, "interval", minutes=15, id="ashby", next_run_time=None)
    scheduler.add_job(poll_lever, "interval", minutes=15, id="lever", next_run_time=None)
    scheduler.add_job(poll_github, "interval", minutes=15, id="github", next_run_time=None)

    # Tier 2: Aggregators - every 30 min
    scheduler.add_job(poll_jobspy_wrapper, "interval", minutes=30, id="jobspy", next_run_time=None)
    scheduler.add_job(poll_amazon_jobs, "interval", minutes=30, id="amazon", next_run_time=None)
    scheduler.add_job(poll_apple_jobs, "interval", minutes=30, id="apple", next_run_time=None)

    # Tier 3: Community - every 60 min
    scheduler.add_job(poll_reddit_feeds, "interval", minutes=60, id="reddit", next_run_time=None)
    scheduler.add_job(poll_workday_feeds, "interval", minutes=60, id="workday", next_run_time=None)

    # Tier 4: Daily
    scheduler.add_job(poll_hn_feeds, "interval", minutes=1440, id="hn", next_run_time=None)

    scheduler.start()
    logger.info("Scheduler started -- all sources armed")

    # Run initial poll — individual failures are logged, not raised
    results = await asyncio.gather(
        poll_greenhouse(), poll_ashby(), poll_lever(),
        poll_github(), poll_amazon_jobs(), poll_apple_jobs(),
        poll_reddit_feeds(), poll_hn_feeds(),
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
