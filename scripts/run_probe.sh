#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
GROUP="${1:-}"
RUN_ID="${2:-}"
[[ -n "$GROUP" && -n "$RUN_ID" ]] || die "usage: $0 <group> <run_id>"
python3 "$ROOT/scripts/run_eval_group.py" "$GROUP" "$RUN_ID" --stage probe
