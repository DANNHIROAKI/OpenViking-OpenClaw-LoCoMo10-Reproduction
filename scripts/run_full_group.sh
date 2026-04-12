#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"

GROUP="${1:-}"
RUN_ID="${2:-}"
WITH_JUDGE="false"

shift_count=0
[[ -n "$GROUP" ]] && shift_count=$((shift_count + 1))
[[ -n "$RUN_ID" ]] && shift_count=$((shift_count + 1))
if [[ "$#" -ge "$shift_count" ]]; then
  shift "$shift_count" || true
fi
for arg in "$@"; do
  case "$arg" in
    --with-judge) WITH_JUDGE="true" ;;
    *) die "unknown argument: $arg" ;;
  esac
done

[[ -n "$GROUP" && -n "$RUN_ID" ]] || die "usage: $0 <group> <run_id> [--with-judge]"

require_runtime_env
[[ "${REPRO_GROUP:-}" == "$GROUP" ]] || die "runtime env group mismatch: expected $GROUP, got ${REPRO_GROUP:-<unset>}"
[[ "${REPRO_RUN_ID:-}" == "$RUN_ID" ]] || die "runtime env run_id mismatch: expected $RUN_ID, got ${REPRO_RUN_ID:-<unset>}"

python3 "$ROOT/scripts/run_eval_group.py" "$GROUP" "$RUN_ID" --stage full
python3 "$ROOT/scripts/finalize_group.py" "$GROUP" "$RUN_ID" --mode full

if [[ "$WITH_JUDGE" == "true" ]]; then
  "$ROOT/scripts/run_judge.sh" "$GROUP" "$RUN_ID" full
fi
