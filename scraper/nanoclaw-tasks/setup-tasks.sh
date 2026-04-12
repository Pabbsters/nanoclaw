#!/bin/bash
# Setup jojo NanoClaw scheduled tasks
# Run this once after deploying the scraper to Fly.io

set -euo pipefail

SCRAPER_URL="${SCRAPER_URL:-https://jojo-scraper.fly.dev}"
IPC_DIR="/Users/ruthwikpabbu/nanoclaw/data/ipc/discord_main/tasks"
DISCORD_JID="discord_main"

mkdir -p "$IPC_DIR"

# Inline enrichment pre-check script (runs before Claude wakes)
# If no new postings since last enrichment, wakeAgent=false saves tokens
ENRICHMENT_SCRIPT='#!/bin/bash
SCRAPER_URL="${SCRAPER_URL:-https://jojo-scraper.fly.dev}"
LAST_TS_FILE="/workspace/group/last_enrichment_ts"
if [ -f "$LAST_TS_FILE" ]; then
  SINCE=$(cat "$LAST_TS_FILE")
else
  SINCE=$(python3 -c "import time; print(int(time.time() - 43200))")
fi
RESULT=$(curl -sf "${SCRAPER_URL}/feed?since=${SINCE}" 2>/dev/null)
if [ $? -ne 0 ] || [ -z "$RESULT" ]; then
  echo "{\"wakeAgent\": false}"
  exit 0
fi
COUNT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get(\"postings\",[])))" 2>/dev/null)
if [ "$COUNT" -gt "0" ]; then
  echo "{\"wakeAgent\": true, \"data\": $RESULT}"
else
  echo "{\"wakeAgent\": false}"
fi'

# Task 1: Daily AI Enrichment (12 PM + 6 PM CST)
# CST is UTC-6, so 12 PM CST = 18:00 UTC, 6 PM CST = 00:00 UTC (next day)
cat > "$IPC_DIR/enrich_$(date +%s).json" << TASK1
{
  "type": "schedule_task",
  "taskId": "jojo-daily-enrichment",
  "prompt": "You are running the daily jojo enrichment task. Your job:\n\n1. Read the scraper feed data provided below. These are new internship postings found in the last 12 hours.\n\n2. For each company with new postings, update or create the company profile at /workspace/extra/vault/companies/{company-slug}.md with:\n   - Company overview (what they do, size, culture)\n   - Open intern roles (from the feed data)\n   - Interview format (search your knowledge + LeetCode patterns)\n   - Common interview questions\n   - Salary/compensation data\n   - Tips for applying\n\n3. Update /workspace/extra/vault/intel/interview-questions.md with any new company-specific questions you find.\n\n4. Update /workspace/extra/vault/intel/market-trends.md with any notable trends (new companies hiring, roles opening up, etc.)\n\n5. Save the current timestamp to /workspace/group/last_enrichment_ts for next run.\n\nBe thorough but concise. Write in a helpful, factual tone. Include specific details that would help Ruthwik prepare for applications and interviews.",
  "script": $(echo "$ENRICHMENT_SCRIPT" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))"),
  "schedule_type": "cron",
  "schedule_value": "0 18,0 * * *",
  "targetJid": "$DISCORD_JID",
  "context_mode": "isolated"
}
TASK1

# Task 2: Weekly Newsletter Draft (Sunday 3 PM CST = 21:00 UTC Sunday)
cat > "$IPC_DIR/newsletter_$(date +%s).json" << 'TASK2'
{
  "type": "schedule_task",
  "taskId": "jojo-weekly-newsletter",
  "prompt": "You are writing the weekly 'Jobs with Ruthwik' LinkedIn newsletter draft.\n\nRuthwik is a Stats + CS + Data Science student at UIUC. This newsletter covers tech recruiting, internship intel, and career advice. It MUST read like Ruthwik wrote it — natural, conversational, no AI tells.\n\nYour process:\n1. Read the scraper feed data from https://jojo-scraper.fly.dev/feed?since=604800 for this week's new postings.\n2. Read /workspace/extra/vault/intel/reddit-weekly.md for Reddit intel.\n3. Read /workspace/extra/vault/intel/market-trends.md for trends.\n\nNewsletter structure (800-1200 words):\n- **Hook**: One big insight or surprising trend from this week\n- **This Week's Top Opportunities**: 3-5 standout internship postings with why they matter\n- **Interview Intel**: What companies are asking right now (LeetCode patterns, behavioral questions)\n- **Market Pulse**: Hiring trends, layoffs, salary movements\n- **One Actionable Takeaway**: Something the reader can do THIS WEEK\n\nVoice guidelines:\n- Write as a fellow student sharing what you found, not as an authority lecturing\n- Use 'I found', 'I noticed', 'from what I'm seeing'\n- Include specific data points and numbers\n- Reference Reddit threads or community discussions naturally\n- Keep paragraphs short (2-3 sentences), use headers and bullets for scannability\n\nSave the draft to /workspace/extra/vault/newsletters/draft-$(date +%Y-%m-%d).md\n\nAlso send a Discord message saying: 'Newsletter draft for this week is ready. Review and post to LinkedIn when ready.'",
  "schedule_type": "cron",
  "schedule_value": "0 21 * * 0",
  "targetJid": "discord_main",
  "context_mode": "isolated"
}
TASK2

# Task 3: Weekly Knowledge Base Update (Saturday 8 AM UTC = 2 AM CST)
cat > "$IPC_DIR/kb_update_$(date +%s).json" << 'TASK3'
{
  "type": "schedule_task",
  "taskId": "jojo-weekly-kb-update",
  "prompt": "You are running the weekly knowledge base update for jojo.\n\nYour tasks:\n\n1. Update /workspace/extra/vault/companies/fortune-500-master.md:\n   - List the top Fortune 500 + FANG companies that hire tech interns\n   - For each company: roles they typically hire for, ATS platform, application timeline, known compensation\n   - Flag any companies with upcoming deadlines\n\n2. Update /workspace/extra/vault/intel/interview-questions.md:\n   - Search your knowledge for current interview questions at target companies\n   - Organize by company, then by role type\n   - Include LeetCode problem numbers/patterns where known\n\n3. Update /workspace/extra/vault/intel/reddit-weekly.md:\n   - Summarize the most valuable posts from r/csMajors, r/cscareerquestions, r/internships this week\n   - Focus on: offer reports, interview experiences, salary data points, company reviews\n   - Include links to the original posts\n\n4. Update /workspace/extra/vault/intel/market-trends.md:\n   - Note any hiring freezes or layoffs from layoffs.fyi\n   - Note salary trend changes\n   - Flag any new companies that started hiring or stopped\n\nBe factual and data-driven. Include dates and sources where possible.",
  "schedule_type": "cron",
  "schedule_value": "0 8 * * 6",
  "targetJid": "discord_main",
  "context_mode": "isolated"
}
TASK3

echo "3 NanoClaw tasks created:"
echo "   1. Daily enrichment (12 PM + 6 PM CST) — with pre-check script"
echo "   2. Weekly newsletter (Sunday 3 PM CST)"
echo "   3. Weekly KB update (Saturday 2 AM CST)"
echo ""
echo "Tasks will be picked up by NanoClaw's IPC watcher within 60 seconds."
echo "Check task status: sqlite3 /Users/ruthwikpabbu/nanoclaw/store/messages.db 'SELECT id, status, next_run FROM scheduled_tasks'"
