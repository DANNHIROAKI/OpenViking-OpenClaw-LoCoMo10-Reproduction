#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

ensure_common_dirs

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  warn ".env not found; copied from .env.example -> $ROOT/.env"
  warn "fill your secrets in .env, then re-run this script if needed"
fi

note "bootstrap step 1/2: fetch upstream repos"
"$ROOT/scripts/fetch_upstreams.sh"

note "bootstrap step 2/2: setup envs"
"$ROOT/scripts/setup_envs.sh"

cat <<EOF

[NEXT]
1. Edit .env and fill the required secrets if you haven't already.
2. Run OpenClaw onboarding once manually:
   openclaw onboard
3. Record versions:
   ./scripts/record_versions.sh
4. Preflight:
   ./scripts/preflight.sh
5. Start phase A smoke:
   ./scripts/phase_a_smoke.sh
EOF
