#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

ensure_common_dirs
require_cmd node
require_cmd openclaw
ensure_eval_venv
ensure_ov_venv

OUT="$ARTIFACTS_DIR/versions.txt"

{
  echo "repo_root: $ROOT"
  echo "node: $(node -v)"
  echo "openclaw: $(openclaw --version)"
  echo "eval_python: $($EVAL_VENV_DIR/bin/python -V 2>&1)"
  echo "ov_python: $($OV_VENV_DIR/bin/python -V 2>&1)"
  echo "openclaw_eval_head: $(git -C "$OPENCLAW_EVAL_DIR" rev-parse HEAD 2>/dev/null || echo missing)"
  echo "openviking_src_head: $(git -C "$OPENVIKING_SRC_DIR" rev-parse HEAD 2>/dev/null || echo missing)"
  echo "openviking_pip_show:"
  "$OV_VENV_DIR/bin/pip" show openviking || true
} > "$OUT"

note "wrote $OUT"
