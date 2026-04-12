#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

ensure_common_dirs
ensure_dataset
ensure_eval_checkout
ensure_eval_venv
require_cmd openclaw
require_env_var OPENCLAW_GATEWAY_TOKEN
require_env_var LANCEDB_EMBEDDING_API_KEY

"$ROOT/scripts/configure_memory_lancedb.sh"

GROUP="row2-memory-lancedb"
SAMPLE="${SMOKE_SAMPLE}"
USER_ID="row2-smoke-s${SAMPLE}"
OUTDIR="$SMOKE_RUNS_DIR/$GROUP"
ensure_dir "$OUTDIR"

INGEST_LOG="$LOG_DIR/${GROUP}.sample${SAMPLE}.ingest.log"
QA_LOG="$LOG_DIR/${GROUP}.sample${SAMPLE}.qa.log"

note "running smoke ingest for $GROUP"
{
  "$EVAL_VENV_DIR/bin/python" "$OPENCLAW_EVAL_DIR/eval.py" ingest "$DATA_PATH" \
    --base-url "$OPENCLAW_BASE_URL" \
    --token "$OPENCLAW_GATEWAY_TOKEN" \
    --sample "$SAMPLE" \
    --sessions "$SMOKE_SESSIONS" \
    --user "$USER_ID" \
    --output "$OUTDIR/ingest.txt"
} 2>&1 | tee "$INGEST_LOG"

note "running smoke qa for $GROUP"
{
  "$EVAL_VENV_DIR/bin/python" "$OPENCLAW_EVAL_DIR/eval.py" qa "$DATA_PATH" \
    --base-url "$OPENCLAW_BASE_URL" \
    --token "$OPENCLAW_GATEWAY_TOKEN" \
    --sample "$SAMPLE" \
    --count "$SMOKE_QA_COUNT" \
    --user "$USER_ID" \
    --output "$OUTDIR/qa.txt"
} 2>&1 | tee "$QA_LOG"

note "done -> $OUTDIR"
