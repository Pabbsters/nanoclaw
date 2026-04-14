# Jojo Internship Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an always-on internship monitoring system that sends Discord alerts and generates weekly newsletter drafts.

**Architecture:** Python scraper on Hetzner (deployed via ComputeEdge MCP) polls 20+ job sources every 15-60 min, stores seen postings in SQLite, sends Discord webhooks for new matches. NanoClaw cron tasks run AI enrichment daily and newsletter generation weekly.

**Tech Stack:** Python 3.12, JobSpy, Playwright, httpx, SQLite, Discord webhooks, ComputeEdge/Hetzner, NanoClaw task scheduler

**Live deployment:** `http://178.104.137.52` · deployment ID `ce-hetzner-031d18a5` · standalone repo `github.com/Pabbsters/jojo-scraper`

---

## File Structure

```
scraper/
├── main.py                    # Entry point, scheduler loop
├── config.py                  # Company lists, role keywords, intervals, Discord webhook URL
├── db.py                      # SQLite operations (seen postings, dedup)
├── discord_alert.py           # Format and send Discord webhook alerts
├── sources/
│   ├── greenhouse.py          # Greenhouse API poller
│   ├── ashby.py               # Ashby API poller
│   ├── lever.py               # Lever API poller
│   ├── github_repos.py        # SimplifyJobs + other GitHub repos
│   ├── jobspy_agg.py          # JobSpy aggregator (LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter)
│   ├── amazon.py              # Amazon Jobs API
│   ├── apple.py               # Apple Jobs API
│   ├── reddit.py              # Reddit JSON API (14 subreddits)
│   ├── hn.py                  # HN Algolia API
│   └── workday.py             # Workday endpoints (Nvidia, Tesla, banks)
├── matching.py                # Role keyword matching + track classification
├── feed.py                    # JSON feed endpoint for NanoClaw
├── requirements.txt
├── Dockerfile
├── fly.toml
└── tests/
    ├── test_matching.py
    ├── test_db.py
    ├── test_discord_alert.py
    ├── test_greenhouse.py
    ├── test_ashby.py
    ├── test_lever.py
    ├── test_github_repos.py
    ├── test_jobspy_agg.py
    └── test_reddit.py
```

---

## Phase 1: Core Scraper Infrastructure

### Task 1: Project Setup & Database

**Files:**
- Create: `scraper/requirements.txt`
- Create: `scraper/config.py`
- Create: `scraper/db.py`
- Create: `scraper/tests/test_db.py`

- [ ] **Step 1: Create requirements.txt**

```
python-jobspy>=1.1.0
httpx>=0.27.0
discord-webhook>=1.3.0
apscheduler>=3.10.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
```

- [ ] **Step 2: Create config.py with company lists and role keywords**

Define TRACK_KEYWORDS dict mapping track names to keyword lists.
Define COMPANY_BOARDS dict mapping company slugs to their ATS type and board ID.
Define DISCORD_WEBHOOK_URL from environment variable.
Define SUBREDDITS list (14 subreddits).
Define polling intervals per source tier.
Define TRACK_PRIORITY list: ["ai_data", "swe", "sales_technical", "consulting", "extras", "cloud_infra"].
Define TRACK_EMOJI mapping tracks to color indicators.

- [ ] **Step 3: Write failing test for db.py**

```python
# scraper/tests/test_db.py
import os
import pytest
from db import PostingDB

@pytest.fixture
def db(tmp_path):
    return PostingDB(str(tmp_path / "test.db"))

def test_is_new_posting_returns_true_for_unseen(db):
    assert db.is_new("greenhouse", "stripe", "swe-intern-123") is True

def test_is_new_posting_returns_false_after_mark_seen(db):
    db.mark_seen("greenhouse", "stripe", "swe-intern-123", "SWE Intern", "https://example.com")
    assert db.is_new("greenhouse", "stripe", "swe-intern-123") is False

def test_get_recent_returns_last_n(db):
    for i in range(5):
        db.mark_seen("greenhouse", "co", f"id-{i}", f"Job {i}", f"https://ex.com/{i}")
    recent = db.get_recent(3)
    assert len(recent) == 3

def test_get_feed_returns_postings_since(db):
    db.mark_seen("greenhouse", "stripe", "j1", "SWE Intern", "https://ex.com/1",
                 track="ai_data", company_name="Stripe", skills="Python, ML")
    feed = db.get_feed_since(0)
    assert len(feed) == 1
    assert feed[0]["title"] == "SWE Intern"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd scraper && python -m pytest tests/test_db.py -v`
Expected: FAIL (no module named db)

- [ ] **Step 5: Implement db.py**

```python
# scraper/db.py
import sqlite3
import time
from typing import Optional

class PostingDB:
    def __init__(self, path: str = "postings.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_postings (
                source TEXT NOT NULL,
                company_slug TEXT NOT NULL,
                posting_id TEXT NOT NULL,
                title TEXT,
                url TEXT,
                track TEXT,
                company_name TEXT,
                skills TEXT,
                comp TEXT,
                team TEXT,
                deadline TEXT,
                seen_at REAL NOT NULL,
                PRIMARY KEY (source, company_slug, posting_id)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_seen_at ON seen_postings(seen_at)
        """)
        self.conn.commit()

    def is_new(self, source: str, company_slug: str, posting_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM seen_postings WHERE source=? AND company_slug=? AND posting_id=?",
            (source, company_slug, posting_id)
        ).fetchone()
        return row is None

    def mark_seen(self, source: str, company_slug: str, posting_id: str,
                  title: str, url: str, track: str = "", company_name: str = "",
                  skills: str = "", comp: str = "", team: str = "",
                  deadline: str = ""):
        self.conn.execute(
            """INSERT OR IGNORE INTO seen_postings
               (source, company_slug, posting_id, title, url, track,
                company_name, skills, comp, team, deadline, seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source, company_slug, posting_id, title, url, track,
             company_name, skills, comp, team, deadline, time.time())
        )
        self.conn.commit()

    def get_recent(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM seen_postings ORDER BY seen_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_feed_since(self, since_ts: float) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM seen_postings WHERE seen_at > ? ORDER BY seen_at DESC",
            (since_ts,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd scraper && python -m pytest tests/test_db.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/requirements.txt scraper/config.py scraper/db.py scraper/tests/test_db.py
git commit -m "feat(scraper): project setup with SQLite dedup database"
```

---

### Task 2: Role Matching Engine

**Files:**
- Create: `scraper/matching.py`
- Create: `scraper/tests/test_matching.py`

- [ ] **Step 1: Write failing test for matching.py**

```python
# scraper/tests/test_matching.py
from matching import classify_posting

def test_ml_engineer_matches_ai_data():
    result = classify_posting("ML Engineer Intern", "Build ML pipelines for recommendations")
    assert result["track"] == "ai_data"
    assert result["priority"] == 1

def test_swe_matches_baseline():
    result = classify_posting("Software Engineer Intern", "General software development")
    assert result["track"] == "swe"
    assert result["priority"] == 2

def test_solutions_architect_matches_sales_technical():
    result = classify_posting("Solutions Architect Intern", "Client-facing technical design")
    assert result["track"] == "sales_technical"
    assert result["priority"] == 3

def test_consultant_matches_consulting():
    result = classify_posting("Technology Consultant Intern", "Strategy consulting for enterprise")
    assert result["track"] == "consulting"
    assert result["priority"] == 4

def test_quant_matches_extras():
    result = classify_posting("Quantitative Developer Intern", "Trading systems")
    assert result["track"] == "extras"
    assert result["priority"] == 5

def test_cloud_engineer_matches_cloud_infra():
    result = classify_posting("Cloud Security Engineer Intern", "AWS security")
    assert result["track"] == "cloud_infra"
    assert result["priority"] == 6

def test_no_match_returns_none():
    result = classify_posting("Marketing Coordinator", "Social media campaigns")
    assert result is None

def test_multiple_track_match_returns_highest_priority():
    result = classify_posting("AI Platform Engineer", "Build ML infrastructure on cloud")
    assert result["track"] == "ai_data"
    assert result["priority"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scraper && python -m pytest tests/test_matching.py -v`
Expected: FAIL

- [ ] **Step 3: Implement matching.py**

```python
# scraper/matching.py
import re
from config import TRACK_KEYWORDS, TRACK_PRIORITY

def classify_posting(title: str, description: str = "") -> dict | None:
    text = f"{title} {description}".lower()
    matches = []
    for track_name, keywords in TRACK_KEYWORDS.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', text):
                priority = TRACK_PRIORITY.index(track_name) + 1 if track_name in TRACK_PRIORITY else 99
                matches.append({"track": track_name, "priority": priority, "matched_keyword": keyword})
                break
    if not matches:
        return None
    matches.sort(key=lambda m: m["priority"])
    return matches[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scraper && python -m pytest tests/test_matching.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/matching.py scraper/tests/test_matching.py
git commit -m "feat(scraper): role matching engine with track classification"
```

---

### Task 3: Discord Alert Sender

**Files:**
- Create: `scraper/discord_alert.py`
- Create: `scraper/tests/test_discord_alert.py`

- [ ] **Step 1: Write failing test**

```python
# scraper/tests/test_discord_alert.py
from discord_alert import format_alert

def test_format_alert_track_1():
    posting = {
        "title": "ML Engineer Intern",
        "company_name": "Anthropic",
        "team": "Research Platform",
        "skills": "Python, PyTorch, distributed systems",
        "deadline": "Rolling",
        "comp": "$65/hr",
        "url": "https://jobs.anthropic.com/123",
        "track": "ai_data",
    }
    msg = format_alert(posting)
    assert "🔴" in msg
    assert "ML Engineer Intern" in msg
    assert "Anthropic" in msg
    assert "https://jobs.anthropic.com/123" in msg

def test_format_alert_track_swe():
    posting = {
        "title": "SWE Intern",
        "company_name": "Google",
        "url": "https://careers.google.com/456",
        "track": "swe",
    }
    msg = format_alert(posting)
    assert "🟠" in msg

def test_format_alert_minimal_fields():
    posting = {
        "title": "Data Analyst Intern",
        "company_name": "Meta",
        "url": "https://metacareers.com/789",
        "track": "ai_data",
    }
    msg = format_alert(posting)
    assert "Data Analyst Intern" in msg
    assert "Meta" in msg
    assert "Team:" not in msg  # should omit missing optional fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scraper && python -m pytest tests/test_discord_alert.py -v`
Expected: FAIL

- [ ] **Step 3: Implement discord_alert.py**

```python
# scraper/discord_alert.py
import os
import httpx
from config import TRACK_EMOJI

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

def format_alert(posting: dict) -> str:
    emoji = TRACK_EMOJI.get(posting.get("track", ""), "⚪")
    lines = [f"{emoji} **NEW: {posting['title']} @ {posting['company_name']}**"]
    if posting.get("team"):
        lines.append(f"Team: {posting['team']}")
    if posting.get("skills"):
        lines.append(f"Skills: {posting['skills']}")
    if posting.get("deadline"):
        lines.append(f"Deadline: {posting['deadline']}")
    if posting.get("comp"):
        lines.append(f"Comp: {posting['comp']}")
    lines.append(f"Link: {posting['url']}")
    company_slug = posting['company_name'].lower().replace(' ', '-')
    lines.append(f"📄 Prep doc → Vault/companies/{company_slug}.md")
    return "\n".join(lines)

async def send_alert(posting: dict):
    if not WEBHOOK_URL:
        return
    message = format_alert(posting)
    async with httpx.AsyncClient() as client:
        await client.post(WEBHOOK_URL, json={"content": message})

async def send_batch_alerts(postings: list[dict]):
    for posting in postings:
        await send_alert(posting)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scraper && python -m pytest tests/test_discord_alert.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/discord_alert.py scraper/tests/test_discord_alert.py
git commit -m "feat(scraper): Discord webhook alert formatter and sender"
```

---

## Phase 2: Data Source Pollers

### Task 4: Greenhouse API Poller

**Files:**
- Create: `scraper/sources/greenhouse.py`
- Create: `scraper/tests/test_greenhouse.py`

- [ ] **Step 1: Write failing test**

```python
# scraper/tests/test_greenhouse.py
import json
import pytest
from sources.greenhouse import parse_greenhouse_jobs, GREENHOUSE_COMPANIES

def test_parse_greenhouse_jobs_extracts_fields():
    raw = {"jobs": [
        {
            "id": 123,
            "title": "Software Engineer Intern",
            "absolute_url": "https://boards.greenhouse.io/citadel/jobs/123",
            "location": {"name": "Chicago, IL"},
            "departments": [{"name": "Engineering"}],
            "content": "Python, distributed systems, algorithms"
        }
    ]}
    results = parse_greenhouse_jobs("citadel", raw)
    assert len(results) == 1
    assert results[0]["posting_id"] == "123"
    assert results[0]["title"] == "Software Engineer Intern"
    assert results[0]["company_slug"] == "citadel"
    assert "https://boards.greenhouse.io/citadel/jobs/123" == results[0]["url"]

def test_greenhouse_companies_includes_key_firms():
    slugs = [c["slug"] for c in GREENHOUSE_COMPANIES]
    assert "citadel" in slugs
    assert "janestreet" in slugs
    assert "twosigma" in slugs
    assert "palantir" in slugs

def test_parse_greenhouse_filters_internships():
    raw = {"jobs": [
        {"id": 1, "title": "Software Engineer Intern", "absolute_url": "https://x.com/1",
         "location": {"name": "NYC"}, "departments": [{"name": "Eng"}], "content": ""},
        {"id": 2, "title": "Senior Software Engineer", "absolute_url": "https://x.com/2",
         "location": {"name": "NYC"}, "departments": [{"name": "Eng"}], "content": ""},
    ]}
    results = parse_greenhouse_jobs("citadel", raw)
    assert len(results) == 1
    assert results[0]["title"] == "Software Engineer Intern"
```

- [ ] **Step 2: Run test, verify fails**
- [ ] **Step 3: Implement greenhouse.py**

Fetch `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`.
Parse jobs, filter for intern/internship/co-op in title.
Return list of normalized posting dicts.
Define GREENHOUSE_COMPANIES list with slugs and display names for: citadel, janestreet, twosigma, deshaw, palantir, databricks, figma, notion, datadog, cloudflare, paloaltonetworks, crowdstrike.

- [ ] **Step 4: Run test, verify passes**
- [ ] **Step 5: Commit**

---

### Task 5: Ashby API Poller (OpenAI, Anthropic, Cohere, Mistral)

**Files:**
- Create: `scraper/sources/ashby.py`
- Create: `scraper/tests/test_ashby.py`

Same pattern as Greenhouse.
Endpoint: `https://api.ashbyhq.com/posting-api/job-board/{slug}`
Filter for intern/internship in title.
Companies: anthropic, openai, cohere, mistralai.

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run test, verify fails**
- [ ] **Step 3: Implement ashby.py**
- [ ] **Step 4: Run test, verify passes**
- [ ] **Step 5: Commit**

---

### Task 6: Lever API Poller (Netflix, SpaceX, Scale AI)

**Files:**
- Create: `scraper/sources/lever.py`
- Create: `scraper/tests/test_lever.py`

Endpoint: `https://api.lever.co/v0/postings/{slug}?mode=json`
Filter for intern/internship in title.
Companies: netflix, spacex, scaleai.

- [ ] Steps 1-5: Same TDD pattern.

---

### Task 7: GitHub Repos Poller (SimplifyJobs + others)

**Files:**
- Create: `scraper/sources/github_repos.py`
- Create: `scraper/tests/test_github_repos.py`

Monitor commits to:
- `SimplifyJobs/Summer2026-Internships` (primary)
- `jobright-ai/2026-Internship`
- `speedyapply/2026-AI-College-Jobs`

Use GitHub API: `GET /repos/{owner}/{repo}/commits?since={last_check}`
Parse commit messages and diff for new company entries.
Also fetch `.github/scripts/listings.json` (SimplifyJobs) for structured data.

- [ ] Steps 1-5: Same TDD pattern.

---

### Task 8: JobSpy Aggregator (LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter)

**Files:**
- Create: `scraper/sources/jobspy_agg.py`
- Create: `scraper/tests/test_jobspy_agg.py`

Use `python-jobspy` library to search across 5 job boards simultaneously.
Search queries: "intern" + each track keyword group.
Rate limit: poll every 30 min, LinkedIn caps at ~10 pages.

```python
from jobspy import scrape_jobs

def poll_jobspy(search_term: str, location: str = "United States",
                results_wanted: int = 50) -> list[dict]:
    jobs = scrape_jobs(
        site_name=["indeed", "linkedin", "glassdoor", "google", "zip_recruiter"],
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        hours_old=24,
    )
    return jobs.to_dict("records")
```

- [ ] Steps 1-5: Same TDD pattern.

---

### Task 9: Amazon & Apple Jobs Pollers

**Files:**
- Create: `scraper/sources/amazon.py`
- Create: `scraper/sources/apple.py`

Amazon: `https://www.amazon.jobs/en/search.json?category=software-dev&schedule=intern`
Apple: `https://jobs.apple.com/api/role/search?key=intern`

- [ ] Steps 1-5: Same TDD pattern.

---

### Task 10: Reddit Poller (14 subreddits)

**Files:**
- Create: `scraper/sources/reddit.py`
- Create: `scraper/tests/test_reddit.py`

Use Reddit JSON API (no auth needed for read-only):
`https://www.reddit.com/r/{subreddit}/new.json?limit=25`

Filter posts by score > 5 and keyword match.
Track seen post IDs in database.

Subreddits: csMajors, cscareerquestions, internships, leetcode, datascience, MachineLearning, UIUC, recruitinghell, experienceddevs, SoftwareEngineerJobs, FAANGrecruiting, SaaS, jobs, forhire.

- [ ] Steps 1-5: Same TDD pattern.

---

### Task 11: HN "Who's Hiring" Poller

**Files:**
- Create: `scraper/sources/hn.py`

Use HN Algolia API:
`https://hn.algolia.com/api/v1/search_by_date?tags=comment,story_{thread_id}&query=intern`

Poll daily. Find the latest "Who's Hiring" thread ID first.

- [ ] Steps 1-5: Same TDD pattern.

---

### Task 12: Workday Poller (Nvidia, Tesla, Banks, Consulting)

**Files:**
- Create: `scraper/sources/workday.py`

Semi-public Workday search API for: nvidia, tesla, jpmorgan, goldmansachs, deloitte, pwc, ey, kpmg, mckinsey, bcg, bain.

This is the most fragile source. Use httpx with retry logic and user-agent spoofing.

- [ ] Steps 1-5: Same TDD pattern.

---

## Phase 3: Scheduler & Feed

### Task 13: Main Scheduler Loop

**Files:**
- Create: `scraper/main.py`

Use APScheduler to run each source on its configured interval.
For each new posting: classify with matching.py → store in db → send Discord alert.

```python
# scraper/main.py
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import PostingDB
from matching import classify_posting
from discord_alert import send_alert
from sources import greenhouse, ashby, lever, github_repos, jobspy_agg, amazon, apple, reddit, hn, workday
from feed import start_feed_server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jojo-scraper")

db = PostingDB()

async def process_postings(postings: list[dict], source: str):
    for p in postings:
        if not db.is_new(source, p.get("company_slug", ""), p["posting_id"]):
            continue
        match = classify_posting(p["title"], p.get("description", ""))
        if match is None:
            continue
        p["track"] = match["track"]
        db.mark_seen(source, p.get("company_slug", ""), p["posting_id"],
                     p["title"], p["url"], track=match["track"],
                     company_name=p.get("company_name", ""),
                     skills=p.get("skills", ""), comp=p.get("comp", ""),
                     team=p.get("team", ""), deadline=p.get("deadline", ""))
        await send_alert(p)
        logger.info(f"New: {p['title']} @ {p.get('company_name', '')} [{match['track']}]")

async def poll_greenhouse():
    for company in greenhouse.GREENHOUSE_COMPANIES:
        postings = await greenhouse.fetch_jobs(company["slug"])
        await process_postings(postings, "greenhouse")

# Similar poll functions for each source...

def main():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(poll_greenhouse, "interval", minutes=15, id="greenhouse")
    scheduler.add_job(poll_ashby, "interval", minutes=15, id="ashby")
    scheduler.add_job(poll_lever, "interval", minutes=15, id="lever")
    scheduler.add_job(poll_github, "interval", minutes=15, id="github")
    scheduler.add_job(poll_jobspy, "interval", minutes=30, id="jobspy")
    scheduler.add_job(poll_amazon_apple, "interval", minutes=30, id="amazon_apple")
    scheduler.add_job(poll_reddit, "interval", minutes=60, id="reddit")
    scheduler.add_job(poll_hn, "interval", minutes=1440, id="hn")  # daily
    scheduler.add_job(poll_workday, "interval", minutes=60, id="workday")
    scheduler.start()
    start_feed_server(db)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()
```

- [ ] **Step 1: Implement main.py**
- [ ] **Step 2: Test locally with one source (greenhouse)**
- [ ] **Step 3: Add all sources**
- [ ] **Step 4: Verify Discord webhook sends real alert**
- [ ] **Step 5: Commit**

---

### Task 14: JSON Feed Server

**Files:**
- Create: `scraper/feed.py`

Simple HTTP endpoint that returns recent postings as JSON for NanoClaw to consume.
Uses built-in `http.server` or a lightweight framework — keeps it minimal.

Endpoint: `GET /feed?since={unix_timestamp}`
Returns: `{"postings": [...], "generated_at": "..."}`

- [ ] Steps 1-5: Same TDD pattern.

---

## Phase 4: Deployment

### Task 15: Dockerize & Deploy via ComputeEdge (Hetzner)

**DONE** — deployed 2026-04-14. Standalone repo: `github.com/Pabbsters/jojo-scraper`

**Files:**
- `scraper/Dockerfile` — Python 3.12-slim + Playwright/Chromium system deps
- `scraper/requirements.txt` — includes `playwright`, `pandas`, `python-jobspy`

- [x] **Step 1: Create Dockerfile** (includes Playwright system deps for LinkedIn/Glassdoor scraping)
- [x] **Step 2: Push to standalone public repo** `github.com/Pabbsters/jojo-scraper`
- [x] **Step 3: Deploy via ComputeEdge MCP**

```python
# Via ComputeEdge MCP (Claude Code)
mcp__computeedge__set_credentials(provider="hetzner", token="<HETZNER_TOKEN>")
mcp__computeedge__set_credentials(key="DISCORD_WEBHOOK_URL", value="<WEBHOOK_URL>")
mcp__computeedge__set_credentials(key="DB_PATH", value="/data/postings.db")
mcp__computeedge__deploy(
    provider_token="<HETZNER_TOKEN>",
    repo_path="https://github.com/Pabbsters/jojo-scraper",
    provider="hetzner"
)
```

- [x] **Step 4: Verify scraper is running**

```python
mcp__computeedge__monitor(deployment_id="ce-hetzner-031d18a5")
# curl http://178.104.137.52/health
# curl http://178.104.137.52/feed
```

- [ ] **Step 5: Verify Discord alert arrives**
- [x] **Step 6: Commit**

---

## Phase 5: NanoClaw Integration

### Task 16: Daily AI Enrichment Task

Create a NanoClaw scheduled task that:
1. Fetches the scraper's JSON feed for new postings
2. For each company with new postings, updates/creates `~/Vault/NanoClaw/companies/{company}.md`
3. Enriches with: team info, interview questions (from LeetCode), salary data, culture notes

Schedule: daily at 12 PM + 6 PM CST via NanoClaw IPC task creation.

- [ ] **Step 1: Write the task script (lightweight check)**

```bash
#!/bin/bash
# Check if scraper has new postings since last run
FEED_URL="${SCRAPER_FEED_URL}/feed?since=$(cat /workspace/group/last_enrichment_ts 2>/dev/null || echo 0)"
RESULT=$(curl -s "$FEED_URL")
COUNT=$(echo "$RESULT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('postings',[])))")
if [ "$COUNT" -gt "0" ]; then
  echo "{\"wakeAgent\": true, \"data\": $RESULT}"
else
  echo "{\"wakeAgent\": false}"
fi
```

- [ ] **Step 2: Create the NanoClaw task via IPC**

Write a JSON file to NanoClaw's IPC directory that schedules the enrichment task with cron `0 12,18 * * *` (12 PM and 6 PM daily).

- [ ] **Step 3: Test the task fires and enriches Vault**
- [ ] **Step 4: Commit**

---

### Task 17: Weekly Newsletter Generation Task

Schedule: Sunday 3 PM CST via NanoClaw cron `0 15 * * 0`.

Task prompt instructs Claude to:
1. Read the week's new postings from scraper feed
2. Read Reddit intel from r/csMajors, r/cscareerquestions
3. Google search for recent LinkedIn pulse articles about recruiting
4. Generate a newsletter draft in Ruthwik's voice
5. Save to `~/Vault/NanoClaw/newsletters/YYYY-MM-DD.md`

- [ ] **Step 1: Write the task script and prompt**
- [ ] **Step 2: Create the NanoClaw task via IPC**
- [ ] **Step 3: Test the task generates a newsletter draft**
- [ ] **Step 4: Commit**

---

### Task 18: Weekly Knowledge Base Update

Schedule: Saturday 2 AM CST via NanoClaw cron `0 2 * * 6`.

Updates:
- `~/Vault/NanoClaw/companies/fortune-500-master.md` — master company list
- `~/Vault/NanoClaw/intel/interview-questions.md` — LeetCode patterns by company
- `~/Vault/NanoClaw/intel/market-trends.md` — layoffs.fyi + levels.fyi data
- `~/Vault/NanoClaw/intel/reddit-weekly.md` — curated Reddit highlights

- [ ] Steps 1-4: Same pattern as Task 16-17.

---

## Phase 6: Testing & Polish

### Task 19: Integration Test

- [ ] **Step 1: Run all scraper tests**

```bash
cd scraper && python -m pytest tests/ -v --tb=short
```

- [ ] **Step 2: Run scraper locally, verify alerts arrive in Discord**
- [ ] **Step 3: Verify Hetzner/ComputeEdge deployment is stable (check logs after 1 hour)**
- [ ] **Step 4: Verify NanoClaw enrichment task fires and writes Vault files**
- [ ] **Step 5: Verify newsletter task generates readable draft**

---

### Task 20: Config Tuning & Documentation

- [ ] **Step 1: Adjust polling intervals based on rate limit observations**
- [ ] **Step 2: Update BUILD.md with scraper setup instructions**
- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: jojo internship alerts system - scraper + NanoClaw integration"
```
