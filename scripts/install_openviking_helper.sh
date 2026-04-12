#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd npm
ensure_ov_venv

note "installing openclaw-openviking-setup-helper"
npm install -g openclaw-openviking-setup-helper

cat <<EOF

[READY]
The helper is installed.

Next, run these commands manually in the repo root:

  export OPENVIKING_PYTHON="$OV_VENV_DIR/bin/python"
  export OPENVIKING_ARK_API_KEY='${OPENVIKING_ARK_API_KEY:-<your_ark_api_key>}'
  ov-install

Inside the interactive flow:
- choose Local mode
- keep the default paths unless you have a reason to change them
- provide your Ark API key

Expected generated files:
- ~/.openviking/ov.conf
- ~/.openclaw/openviking.env
EOF
