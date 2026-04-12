#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

ensure_common_dirs
ensure_dataset
ensure_targets
require_cmd python3
require_cmd git
require_cmd npm
require_cmd node
require_cmd "$EVAL_PYTHON"
require_cmd "$OV_PYTHON"

if [[ -f "$ROOT/.env" ]]; then
  note "loaded .env"
else
  warn ".env not found; falling back to defaults / exported env vars"
fi

python3 "$ROOT/scripts/check_dataset.py"

if [[ -d "$OPENCLAW_EVAL_DIR" ]]; then
  note "found openclaw-eval checkout: $OPENCLAW_EVAL_DIR"
else
  warn "missing openclaw-eval checkout; run ./scripts/fetch_upstreams.sh"
fi

if [[ -f "$EVAL_VENV_DIR/bin/python" ]]; then
  note "found eval venv: $EVAL_VENV_DIR"
else
  warn "missing eval venv; run ./scripts/setup_envs.sh"
fi

if [[ -f "$OV_VENV_DIR/bin/python" ]]; then
  note "found OpenViking venv: $OV_VENV_DIR"
else
  warn "missing OpenViking venv; run ./scripts/setup_envs.sh"
fi

for var in OPENCLAW_GATEWAY_TOKEN OPENVIKING_ARK_API_KEY JUDGE_BASE_URL JUDGE_API_KEY JUDGE_MODEL; do
  if [[ -n "${!var:-}" ]]; then
    note "$var is set"
  else
    warn "$var is empty"
  fi
done

if [[ -n "${LANCEDB_EMBEDDING_API_KEY:-}" ]]; then
  note "LANCEDB_EMBEDDING_API_KEY is set"
else
  warn "LANCEDB_EMBEDDING_API_KEY is empty (needed for row2)"
fi

if command -v openclaw >/dev/null 2>&1; then
  note "openclaw version: $(openclaw --version 2>/dev/null || echo unknown)"
else
  warn "openclaw not found; run ./scripts/setup_envs.sh"
fi

cat <<MSG

[NEXT]
1. If upstream repos are missing: ./scripts/fetch_upstreams.sh
2. If venvs or openclaw are missing: ./scripts/setup_envs.sh
3. If everything above looks good: ./scripts/smoke_row1_memory_core.sh
MSG
