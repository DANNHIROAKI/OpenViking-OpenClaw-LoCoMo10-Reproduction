#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd openclaw
ensure_common_dirs
require_env_var LANCEDB_EMBEDDING_API_KEY

note "configuring OpenClaw to use memory-lancedb"
openclaw config set plugins.enabled true --json
openclaw config set plugins.entries.memory-lancedb.enabled true --json || true
openclaw config set plugins.slots.memory memory-lancedb
openclaw config set plugins.entries.memory-lancedb.config.autoRecall true --json
openclaw config set plugins.entries.memory-lancedb.config.autoCapture true --json
openclaw config set plugins.entries.memory-lancedb.config.embedding.apiKey "$LANCEDB_EMBEDDING_API_KEY"
openclaw config set plugins.entries.memory-lancedb.config.embedding.model "$LANCEDB_EMBEDDING_MODEL"

if [[ -n "${LANCEDB_DB_PATH:-}" ]]; then
  openclaw config set plugins.entries.memory-lancedb.config.dbPath "$LANCEDB_DB_PATH" || true
fi

if [[ -n "${LANCEDB_EMBEDDING_BASE_URL:-}" ]]; then
  warn "LANCEDB_EMBEDDING_BASE_URL is set, but many OpenClaw versions reject embedding.baseUrl in the schema."
  warn "If you need it, try setting it manually after checking your installed OpenClaw version."
fi

openclaw gateway restart
openclaw status | tee "$ARTIFACTS_DIR/openclaw-status.memory-lancedb.txt"
