#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

GROUP="${1:-}"
EXPECTED="${2:-1540}"
[[ -n "$GROUP" ]] || die "usage: $0 <group> [expected_count]"

python3 "$ROOT/scripts/merge_answers.py" "$GROUP" --expected "$EXPECTED"
python3 "$ROOT/scripts/sum_input_tokens.py" "$GROUP"
"$ROOT/scripts/judge_group.sh" "$GROUP"
python3 "$ROOT/scripts/verify_group_outputs.py" "$GROUP" --expected "$EXPECTED"
