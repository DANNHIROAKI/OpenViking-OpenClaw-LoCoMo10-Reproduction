#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd openclaw
ensure_common_dirs

PLUGINS_OUT="$(openclaw_artifact openclaw.plugins.list.txt)"
STATUS_OUT="$(openclaw_artifact openclaw.status.txt)"
CONFIG_OUT="$(openclaw_artifact openclaw.plugins.config.txt)"
SLOTS_OUT="$(openclaw_artifact openclaw.plugins.slots.txt)"

openclaw plugins list > "$PLUGINS_OUT" 2>&1 || true
openclaw status > "$STATUS_OUT" 2>&1 || true
{
  echo '--- plugins ---'
  openclaw config get plugins 2>&1 || true
  echo
  echo '--- plugins.slots ---'
  openclaw config get plugins.slots 2>&1 || true
  echo
  echo '--- plugins.entries.memory-lancedb ---'
  openclaw config get plugins.entries.memory-lancedb 2>&1 || true
  echo
  echo '--- plugins.entries.memory-openviking ---'
  openclaw config get plugins.entries.memory-openviking 2>&1 || true
} > "$CONFIG_OUT"
openclaw config get plugins.slots > "$SLOTS_OUT" 2>&1 || true

note "wrote $PLUGINS_OUT"
note "wrote $STATUS_OUT"
note "wrote $CONFIG_OUT"
note "wrote $SLOTS_OUT"
