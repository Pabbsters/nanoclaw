#!/bin/bash
# Add Vault mount to discord_main group's container config
# This allows jojo's NanoClaw tasks to read/write ~/Vault/NanoClaw/
#
# The mount maps:
#   Host: ~/Vault/NanoClaw -> Container: /workspace/extra/vault
#
# Run this once before the enrichment tasks need Vault access.

set -euo pipefail

IPC_DIR="/Users/ruthwikpabbu/nanoclaw/data/ipc/discord_main/tasks"
mkdir -p "$IPC_DIR"

cat > "$IPC_DIR/vault_mount_$(date +%s).json" << EOF
{
  "type": "register_group",
  "jid": "discord_main",
  "name": "Discord Main",
  "folder": "discord_main",
  "trigger": "@Andy",
  "requiresTrigger": false,
  "containerConfig": {
    "additionalMounts": [
      {
        "hostPath": "${HOME}/Vault/NanoClaw",
        "containerPath": "vault",
        "readonly": false
      }
    ]
  }
}
EOF

echo "Vault mount configured for discord_main containers"
echo "   Host: ~/Vault/NanoClaw -> Container: /workspace/extra/vault"
echo "   NanoClaw will pick this up within 60 seconds."
