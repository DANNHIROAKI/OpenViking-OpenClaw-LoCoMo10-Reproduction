#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

note "phase A: preflight + row1 smoke + row3 smoke"
"$ROOT/scripts/preflight.sh"
"$ROOT/scripts/smoke_row1_memory_core.sh"

ENV_FILE="$HOME/.openclaw/openviking.env"
if [[ ! -f "$ENV_FILE" ]]; then
  warn "OpenViking helper env not found: $ENV_FILE"
  cat <<MSG

[ACTION REQUIRED]
Run these commands, then re-run ./scripts/phase_a_smoke.sh

  ./scripts/install_openviking_helper.sh
  export OPENVIKING_PYTHON="$ROOT/.venv-ov/bin/python"
  export OPENVIKING_ARK_API_KEY='your_ark_key'
  ov-install

MSG
  exit 2
fi

"$ROOT/scripts/configure_openviking_local.sh"
"$ROOT/scripts/smoke_row3_openviking_minus_core.sh"
python3 "$ROOT/scripts/status_matrix.py"
