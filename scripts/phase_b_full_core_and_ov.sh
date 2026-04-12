#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

note "phase B: full row1 + row3, then finalize + summary"

"$ROOT/scripts/run_full_group.sh" row1-memory-core
"$ROOT/scripts/run_full_group.sh" row3-openviking-minus-core

"$ROOT/scripts/finalize_group.sh" row1-memory-core 1540
"$ROOT/scripts/finalize_group.sh" row3-openviking-minus-core 1540
python3 "$ROOT/scripts/build_results_table.py"
python3 "$ROOT/scripts/status_matrix.py"
