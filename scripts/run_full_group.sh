#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

GROUP="${1:-}"
[[ -n "$GROUP" ]] || die "usage: $0 <row1-memory-core|row3-openviking-minus-core>"

ensure_common_dirs
ensure_dataset
ensure_eval_checkout
ensure_eval_venv
require_cmd openclaw
require_env_var OPENCLAW_GATEWAY_TOKEN

case "$GROUP" in
  row1-memory-core)
    "$ROOT/scripts/configure_memory_core.sh"
    ;;
  row3-openviking-minus-core)
    "$ROOT/scripts/configure_openviking_local.sh"
    ;;
  *)
    die "unsupported group: $GROUP"
    ;;
esac

SAMPLES="${SAMPLES:-0 1 2 3 4 5 6 7 8 9}"
OUTROOT="$FULL_RUNS_DIR/$GROUP"
ensure_dir "$OUTROOT"

for SAMPLE in $SAMPLES; do
  USER_ID="${GROUP}-sample-${SAMPLE}"
  OUTDIR="$OUTROOT/sample_${SAMPLE}"
  ensure_dir "$OUTDIR"

  INGEST_LOG="$LOG_DIR/${GROUP}.sample${SAMPLE}.ingest.log"
  QA_LOG="$LOG_DIR/${GROUP}.sample${SAMPLE}.qa.log"

  note "[$GROUP] ingest sample=$SAMPLE user=$USER_ID"
  {
    "$EVAL_VENV_DIR/bin/python" "$OPENCLAW_EVAL_DIR/eval.py" ingest "$DATA_PATH" \
      --base-url "$OPENCLAW_BASE_URL" \
      --token "$OPENCLAW_GATEWAY_TOKEN" \
      --sample "$SAMPLE" \
      --user "$USER_ID" \
      --output "$OUTDIR/ingest.txt"
  } 2>&1 | tee "$INGEST_LOG"

  note "[$GROUP] qa sample=$SAMPLE user=$USER_ID"
  {
    "$EVAL_VENV_DIR/bin/python" "$OPENCLAW_EVAL_DIR/eval.py" qa "$DATA_PATH" \
      --base-url "$OPENCLAW_BASE_URL" \
      --token "$OPENCLAW_GATEWAY_TOKEN" \
      --sample "$SAMPLE" \
      --user "$USER_ID" \
      --output "$OUTDIR/qa.txt"
  } 2>&1 | tee "$QA_LOG"
done

note "full run finished: $OUTROOT"
