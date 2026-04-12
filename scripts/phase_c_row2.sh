#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_env_var LANCEDB_EMBEDDING_API_KEY
note "phase C: patch + smoke + full row2, then merge/token/judge/summary"

"$ROOT/scripts/patch_memory_lancedb_global.sh"
"$ROOT/scripts/smoke_row2_lancedb.sh"
"$ROOT/scripts/run_full_group.sh" row2-memory-lancedb
python3 "$ROOT/scripts/merge_answers.py" row2-memory-lancedb --expected 1540
python3 "$ROOT/scripts/sum_input_tokens.py" row2-memory-lancedb
"$ROOT/scripts/judge_group.sh" row2-memory-lancedb
python3 "$ROOT/scripts/build_results_table.py"
python3 "$ROOT/scripts/status_matrix.py"
