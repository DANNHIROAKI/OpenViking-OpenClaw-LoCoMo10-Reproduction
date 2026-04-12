#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
GROUP="${1:-}"
RUN_ID="${2:-}"
[[ -n "$GROUP" && -n "$RUN_ID" ]] || die "usage: $0 <group> <run_id>"
require_runtime_env
[[ "${REPRO_GROUP:-}" == "$GROUP" ]] || die "runtime env group mismatch: expected $GROUP, got ${REPRO_GROUP:-<unset>}"
[[ "${REPRO_RUN_ID:-}" == "$RUN_ID" ]] || die "runtime env run_id mismatch: expected $RUN_ID, got ${REPRO_RUN_ID:-<unset>}"
python3 "$ROOT/scripts/run_eval_group.py" "$GROUP" "$RUN_ID" --stage probe
