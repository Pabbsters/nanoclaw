#!/bin/bash
# Pre-check script for daily enrichment
# Runs before Claude agent wakes — checks if scraper has new postings
# If no new postings found, outputs wakeAgent=false to save tokens

SCRAPER_URL="${SCRAPER_URL:-http://178.104.199.240}"
LAST_TS_FILE="/workspace/group/last_enrichment_ts"

# Get timestamp of last enrichment (default: 12 hours ago)
if [ -f "$LAST_TS_FILE" ]; then
    SINCE=$(cat "$LAST_TS_FILE")
else
    SINCE=$(python3 -c "import time; print(int(time.time() - 43200))")
fi

# Fetch new postings from scraper
RESULT=$(curl -sf "${SCRAPER_URL}/feed?since=${SINCE}" 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$RESULT" ]; then
    echo '{"wakeAgent": false}'
    exit 0
fi

COUNT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('postings',[])))" 2>/dev/null)

if [ "$COUNT" -gt "0" ]; then
    echo "{\"wakeAgent\": true, \"data\": $RESULT}"
else
    echo '{"wakeAgent": false}'
fi
