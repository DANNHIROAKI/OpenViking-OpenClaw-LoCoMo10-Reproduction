#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
GROUP="${1:-}"
RUN_ID="${2:-}"
STAGE="${3:-}"
[[ -n "$GROUP" && -n "$RUN_ID" && -n "$STAGE" ]] || die "usage: $0 <group> <run_id> <micro|extended>"
[[ "$STAGE" == "micro" || "$STAGE" == "extended" ]] || die "stage must be micro or extended"
require_runtime_env
[[ "${REPRO_GROUP:-}" == "$GROUP" ]] || die "runtime env group mismatch: expected $GROUP, got ${REPRO_GROUP:-<unset>}"
[[ "${REPRO_RUN_ID:-}" == "$RUN_ID" ]] || die "runtime env run_id mismatch: expected $RUN_ID, got ${REPRO_RUN_ID:-<unset>}"
python3 "$ROOT/scripts/run_eval_group.py" "$GROUP" "$RUN_ID" --stage "$STAGE"
python3 "$ROOT/scripts/finalize_group.py" "$GROUP" "$RUN_ID" --mode smoke --stage "$STAGE"
