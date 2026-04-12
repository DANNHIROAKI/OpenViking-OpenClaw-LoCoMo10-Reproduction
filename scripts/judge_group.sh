#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

GROUP="${1:-}"
[[ -n "$GROUP" ]] || die "usage: $0 <group>"

ensure_common_dirs
ensure_eval_checkout
ensure_eval_venv
require_env_var JUDGE_BASE_URL
require_env_var JUDGE_API_KEY
require_env_var JUDGE_MODEL

ANSWERS="$ARTIFACTS_DIR/${GROUP}.answers.json"
if [[ ! -f "$ANSWERS" ]]; then
  note "answers file missing; merging now"
  python3 "$ROOT/scripts/merge_answers.py" "$GROUP"
fi

OUT="$ARTIFACTS_DIR/${GROUP}.grades.json"

"$EVAL_VENV_DIR/bin/python" "$OPENCLAW_EVAL_DIR/judge.py" "$ANSWERS" \
  --output "$OUT" \
  --base-url "$JUDGE_BASE_URL" \
  --token "$JUDGE_API_KEY" \
  --model "$JUDGE_MODEL"

note "wrote $OUT"
