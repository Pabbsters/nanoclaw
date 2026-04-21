#!/bin/bash
# Create Vault directory structure for jojo NanoClaw tasks
# Run this once before setting up tasks

set -euo pipefail

VAULT_BASE="${HOME}/Vault/NanoClaw"

mkdir -p "$VAULT_BASE/companies"
mkdir -p "$VAULT_BASE/newsletters"
mkdir -p "$VAULT_BASE/intel"
mkdir -p "$VAULT_BASE/scraper-feed"
mkdir -p "$VAULT_BASE/uiuc-scout/openings"
mkdir -p "$VAULT_BASE/uiuc-scout/labs"
mkdir -p "$VAULT_BASE/uiuc-scout/outreach"
mkdir -p "$VAULT_BASE/uiuc-scout/quant"

# Create initial placeholder files if they don't exist
[ -f "$VAULT_BASE/companies/fortune-500-master.md" ] || cat > "$VAULT_BASE/companies/fortune-500-master.md" << 'EOF'
# Fortune 500 + FANG Companies — Intern Hiring

**Last updated**: (will be updated by jojo weekly task)

## Companies by ATS Platform

### Greenhouse
- Citadel, Jane Street, Two Sigma, DE Shaw, Palantir, Databricks, Figma, Notion, Datadog, Cloudflare

### Ashby
- Anthropic, OpenAI, Cohere, Mistral AI

### Lever
- Netflix, SpaceX, Scale AI

### Workday
- Nvidia, Tesla, JPMorgan, Goldman Sachs, Deloitte

### Custom
- Google, Apple, Amazon, Microsoft, Meta
EOF

[ -f "$VAULT_BASE/intel/interview-questions.md" ] || cat > "$VAULT_BASE/intel/interview-questions.md" << 'EOF'
# Interview Questions by Company

**Last updated**: (will be updated by jojo weekly task)

*This file is auto-updated by jojo's weekly knowledge base task.*
EOF

[ -f "$VAULT_BASE/intel/market-trends.md" ] || cat > "$VAULT_BASE/intel/market-trends.md" << 'EOF'
# Market Trends

**Last updated**: (will be updated by jojo weekly task)

*This file is auto-updated by jojo's weekly knowledge base task.*
EOF

[ -f "$VAULT_BASE/intel/reddit-weekly.md" ] || cat > "$VAULT_BASE/intel/reddit-weekly.md" << 'EOF'
# Reddit Weekly Intel

**Last updated**: (will be updated by jojo weekly task)

*This file is auto-updated by jojo's weekly knowledge base task.*
EOF

[ -f "$VAULT_BASE/uiuc-scout/queue.md" ] || cat > "$VAULT_BASE/uiuc-scout/queue.md" << 'EOF'
# UIUC Scout Queue

This file is auto-updated by the UIUC scout pipeline.
EOF

[ -f "$VAULT_BASE/uiuc-scout/sources.md" ] || cat > "$VAULT_BASE/uiuc-scout/sources.md" << 'EOF'
# UIUC Scout Sources

This file is auto-updated by the UIUC scout pipeline.
EOF

echo "Vault structure created at $VAULT_BASE"
ls -la "$VAULT_BASE"
echo ""
ls -la "$VAULT_BASE/companies/"
echo ""
ls -la "$VAULT_BASE/intel/"
