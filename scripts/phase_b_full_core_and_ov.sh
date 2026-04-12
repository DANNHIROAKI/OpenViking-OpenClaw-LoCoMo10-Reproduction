#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

note "phase B: full row1 + row3, then merge/token/judge/summary"

"$ROOT/scripts/run_full_group.sh" row1-memory-core
"$ROOT/scripts/run_full_group.sh" row3-openviking-minus-core

python3 "$ROOT/scripts/merge_answers.py" row1-memory-core --expected 1540
python3 "$ROOT/scripts/merge_answers.py" row3-openviking-minus-core --expected 1540
python3 "$ROOT/scripts/sum_input_tokens.py" row1-memory-core
python3 "$ROOT/scripts/sum_input_tokens.py" row3-openviking-minus-core
"$ROOT/scripts/judge_group.sh" row1-memory-core
"$ROOT/scripts/judge_group.sh" row3-openviking-minus-core
python3 "$ROOT/scripts/build_results_table.py"
python3 "$ROOT/scripts/status_matrix.py"
