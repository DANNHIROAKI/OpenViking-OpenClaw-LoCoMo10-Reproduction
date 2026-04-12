#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/common.sh"
GROUP="${1:-}"
RUN_ID="${2:-}"
MODE="${3:-full}"
STAGE="${4:-}"
[[ -n "$GROUP" && -n "$RUN_ID" ]] || die "usage: $0 <group> <run_id> [full|smoke] [stage]"
RUN_ROOT="$ROOT/runs/$MODE/$RUN_ID/$GROUP"
if [[ "$MODE" == "smoke" ]]; then
  [[ -n "$STAGE" ]] || die "smoke mode requires stage"
  RUN_ROOT="$ROOT/runs/smoke/$RUN_ID/$GROUP/$STAGE"
fi
INPUT="$RUN_ROOT/merged_answers.json"
OUTPUT="$RUN_ROOT/grades.json"
LOG="$RUN_ROOT/judge.console.log"
[[ -f "$INPUT" ]] || die "missing merged answers: $INPUT"

SPEC_ARGS=("$GROUP" "$RUN_ID" --mode "$MODE")
if [[ -n "$STAGE" ]]; then
  SPEC_ARGS+=(--stage "$STAGE")
fi
python3 "$ROOT/scripts/write_judge_run_spec.py" "${SPEC_ARGS[@]}"

PYTHONPATH="$ROOT/vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888" \
python3 "$ROOT/vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge.py" \
  "$INPUT" \
  --output "$OUTPUT" \
  --base-url "${JUDGE_BASE_URL:-}" \
  --token "${JUDGE_API_KEY:-}" \
  --model "${JUDGE_MODEL:-gpt-4o-mini}" \
  2>&1 | tee "$LOG"

if [[ "$MODE" == "full" ]]; then
  python3 "$ROOT/scripts/finalize_group.py" "$GROUP" "$RUN_ID" --mode full
  python3 "$ROOT/scripts/verify_group_outputs.py" "$GROUP" "$RUN_ID" --mode full --require-judge
else
  python3 "$ROOT/scripts/finalize_group.py" "$GROUP" "$RUN_ID" --mode smoke --stage "$STAGE"
  python3 "$ROOT/scripts/verify_group_outputs.py" "$GROUP" "$RUN_ID" --mode smoke --stage "$STAGE" --require-judge
fi
