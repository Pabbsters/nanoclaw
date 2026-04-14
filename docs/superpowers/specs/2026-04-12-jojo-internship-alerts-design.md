# Jojo Internship Alerts & Newsletter System — Design Spec

**Author**: Ruthwik Pabbu
**Date**: 2026-04-12
**Status**: Approved

---

## Overview

An always-on job monitoring and career intelligence system that:
1. Scrapes internship postings from 20+ sources every 15-60 minutes
2. Sends instant Discord alerts to Ruthwik's phone in a mobile-friendly format
3. Maintains an enriched knowledge base in Obsidian Vault (company profiles, interview prep, salary data)
4. Generates a weekly LinkedIn newsletter draft ("Jobs with Ruthwik")

## User Profile

- **Name**: Ruthwik Pabbu
- **Background**: Stats + CS + Data Science @ UIUC
- **Primary career track**: AI/Data (AI Engineer, ML Engineer, Data Engineer, Data Scientist, NLP, MLOps, CV, Research Eng)
- **Secondary track**: Cloud/Infra/Security
- **Baseline**: SWE (always applicable)
- **Additional tracks**: Product/Leadership (consulting: MBB + Big 4), Sales/Client-Facing Technical, Extras (Quant, Robotics, Fintech)

## Alert Priority Order

1. Track 1 — AI/Data
2. Track 3 — SWE (Baseline)
3. Track 5 — Sales/Client-Facing Technical
4. Track 4 — Product/Business/Leadership (MBB + Big 4 consulting focus)
5. Track 6 — Extras/High-Upside
6. Track 2 — Cloud/Infra/Security

---

## Architecture: Hybrid (Two Layers)

### Layer 1 — Scraper (ComputeEdge/Hetzner, always-on, $3.49/mo)

A Python service deployed on Hetzner via ComputeEdge MCP at `http://178.104.137.52` that:
- Polls job board APIs and aggregators on intervals (15-60 min)
- Tracks seen postings in SQLite to avoid duplicates
- Matches postings against role keywords organized by career track
- Sends Discord webhook alerts in Format B when new matches found
- Exposes a JSON feed of new postings for NanoClaw to consume

**Tech stack**: Python 3.12, JobSpy, aiohttp/httpx, SQLite, Discord webhook

### Layer 2 — AI Brain (NanoClaw, daytime on laptop)

NanoClaw scheduled tasks that:
- **Daily (12 PM + 6 PM CST)**: Read new postings feed, enrich Vault company docs
- **Weekly (Sunday 3 PM CST)**: Generate newsletter draft
- **Weekly**: Update Fortune 500 master doc + interview questions
- **On-demand**: Respond to Discord messages ("prep me for Stripe SWE")

---

## Data Sources

### Tier 1 — Direct Company APIs (15 min poll)

| API | Companies |
|-----|-----------|
| Greenhouse | Citadel, Jane Street, Two Sigma, DE Shaw, Palantir, Databricks, Figma, Notion, Datadog, Cloudflare |
| Ashby | Anthropic, OpenAI, Cohere, Mistral |
| Lever | Netflix, SpaceX, Scale AI |
| Amazon Jobs | Amazon, AWS |
| Apple Jobs | Apple |

### Tier 2 — Aggregators (30 min poll)

| Source | Coverage |
|--------|----------|
| JobSpy (Python) | LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter |
| SimplifyJobs GitHub | 500+ companies, structured JSON |
| jobright-ai/2026-Internship GitHub | AI-curated, all industries |
| speedyapply/2026-AI-College-Jobs GitHub | AI/ML specific |
| intern-list.com | Hourly from 200K+ career sites |

### Tier 3 — Fragile/Custom Scraping (60 min poll)

| Source | Companies |
|--------|-----------|
| Google Careers JSON | Google, DeepMind |
| Microsoft Careers | Microsoft |
| Workday endpoints | Nvidia, Tesla, JPMorgan, Goldman Sachs |
| LinkedIn guest endpoint | Job listings without login |
| McKinsey/BCG/Bain career pages | MBB consulting |
| Deloitte/PwC/EY/KPMG | Big 4 consulting |

### Tier 4 — Community Intel (60 min poll)

14 subreddits via Reddit JSON API:
r/csMajors, r/cscareerquestions, r/internships, r/leetcode, r/datascience, r/MachineLearning, r/UIUC, r/recruitinghell, r/experienceddevs, r/SoftwareEngineerJobs, r/FAANGrecruiting, r/SaaS, r/jobs, r/forhire

### Tier 5 — Interview & Salary Intel (daily)

- LeetCode Discuss (GraphQL API)
- HN "Who's Hiring" (Algolia API)
- levels.fyi (key pages)
- layoffs.fyi (hiring freezes)

### Tier 6 — Social Media (weekly, AI enrichment)

- LinkedIn posts/newsletters: Google `site:linkedin.com/pulse` queries
- X/Twitter: RSS bridges for ~20 curated recruiter accounts
- Blind: Google `site:teamblind.com` queries

---

## Discord Alert Format (Format B)

```
🔴 NEW: SWE Intern @ Stripe
Team: Payment Infrastructure
Skills: Python, distributed systems, API design
Deadline: Rolling (apply fast)
Comp: ~$55/hr
Link: https://jobs.stripe.com/...
📄 Prep doc → Vault/companies/stripe.md
```

Priority tiers affect formatting:
- Track 1 (AI/Data): 🔴 red indicator
- Track 3 (SWE): 🟠 orange
- Track 5 (Sales/Technical): 🟡 yellow
- Track 4 (Consulting): 🔵 blue
- Track 6 (Extras): 🟢 green
- Track 2 (Cloud/Infra): ⚪ white

---

## Vault Structure

```
~/Vault/NanoClaw/
├── career-plan/
│   ├── career-tracks.md          (already created)
│   └── grad-school-plan.md       (already created)
├── jojo-project/
│   ├── design-spec.md            (copy of this spec)
│   └── session-context.md        (conversation context for future sessions)
├── companies/
│   ├── {company-slug}.md         (per-company: team info, interview Qs, salary, culture)
│   └── fortune-500-master.md     (master list + interview questions, updated weekly)
├── newsletters/
│   └── YYYY-MM-DD.md             (weekly newsletter drafts)
├── intel/
│   ├── reddit-weekly.md          (curated Reddit intel)
│   ├── interview-questions.md    (cross-company LeetCode/interview patterns)
│   └── market-trends.md          (layoffs, hiring freezes, salary trends)
└── scraper-feed/
    └── latest.json               (JSON feed for NanoClaw to consume)
```

---

## Newsletter: "Jobs with Ruthwik"

- **Cadence**: Weekly (Sunday)
- **Output**: `~/Vault/NanoClaw/newsletters/YYYY-MM-DD.md`
- **Ruthwik copy-pastes to LinkedIn manually**
- **Voice**: Must read like Ruthwik wrote it — no AI tells
- **Structure**: One big insight/trend + 3-5 curated data points + one actionable takeaway
- **Length**: 800-1200 words, scannable with headers and bullets
- **Sources**: Job posting trends, Reddit intel, interview reports, salary data, market signals

---

## Deployment

- **Scraper**: Hetzner CX23 via ComputeEdge MCP (256MB RAM, 38GB disk) — `http://178.104.137.52`, deployment `ce-hetzner-031d18a5`, repo `github.com/Pabbsters/jojo-scraper`
- **NanoClaw tasks**: Existing launchd service on macOS
- **Discord**: Webhook for alerts (no bot needed for outbound-only)
- **Cost**: $3.49/mo

---

## Out of Scope (v1)

- Auto-applying to jobs
- LinkedIn post automation (manual copy-paste only)
- Real-time LinkedIn/X post monitoring (weekly via Google search instead)
- Handshake integration (requires .edu auth — add in v2)
- Referral tracker (needs LinkedIn network access — add in v2)
- Resume tailoring (add in v2 after knowledge base is populated)
