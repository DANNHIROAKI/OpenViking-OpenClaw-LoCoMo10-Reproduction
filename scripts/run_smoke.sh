#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
GROUP="${1:-}"
RUN_ID="${2:-}"
STAGE="${3:-}"
[[ -n "$GROUP" && -n "$RUN_ID" && -n "$STAGE" ]] || die "usage: $0 <group> <run_id> <micro|extended>"
[[ "$STAGE" == "micro" || "$STAGE" == "extended" ]] || die "stage must be micro or extended"
python3 "$ROOT/scripts/run_eval_group.py" "$GROUP" "$RUN_ID" --stage "$STAGE"
python3 "$ROOT/scripts/finalize_group.py" "$GROUP" "$RUN_ID" --mode smoke --stage "$STAGE"
