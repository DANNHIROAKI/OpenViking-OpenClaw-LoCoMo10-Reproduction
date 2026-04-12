#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_env_var LANCEDB_EMBEDDING_API_KEY
note "phase C: patch + smoke + full row2, then finalize + summary"

"$ROOT/scripts/patch_memory_lancedb_global.sh"
"$ROOT/scripts/smoke_row2_lancedb.sh"
"$ROOT/scripts/run_full_group.sh" row2-memory-lancedb
"$ROOT/scripts/finalize_group.sh" row2-memory-lancedb 1540
python3 "$ROOT/scripts/build_results_table.py"
python3 "$ROOT/scripts/status_matrix.py"
