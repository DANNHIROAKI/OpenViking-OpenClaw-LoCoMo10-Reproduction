#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

ensure_common_dirs
require_cmd npm
require_cmd "$EVAL_PYTHON"
require_cmd "$OV_PYTHON"
ensure_eval_checkout

note "installing OpenClaw $OPENCLAW_VERSION"
npm install -g "openclaw@${OPENCLAW_VERSION}"

note "creating eval venv: $EVAL_VENV_DIR"
"$EVAL_PYTHON" -m venv "$EVAL_VENV_DIR"
"$EVAL_VENV_DIR/bin/python" -m pip install -U pip
"$EVAL_VENV_DIR/bin/pip" install \
  "openai>=1.0.0" \
  "pydantic>=2.0.0" \
  "python-dotenv>=1.0.0" \
  "requests>=2.32.5"

note "creating OpenViking venv: $OV_VENV_DIR"
"$OV_PYTHON" -m venv "$OV_VENV_DIR"
"$OV_VENV_DIR/bin/python" -m pip install -U pip
"$OV_VENV_DIR/bin/pip" install "openviking==${OPENVIKING_VERSION}"

cat <<EOF

[NEXT]
1. Run this once manually:
   openclaw onboard

2. Then record versions:
   ./scripts/record_versions.sh

3. Then validate the dataset:
   python3 scripts/check_dataset.py
EOF
