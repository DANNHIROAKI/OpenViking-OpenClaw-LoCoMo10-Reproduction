#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd openclaw
ensure_common_dirs

note "configuring OpenClaw to use memory-core"
openclaw config set plugins.enabled true --json
openclaw config set plugins.slots.memory memory-core
openclaw gateway restart
openclaw status | tee "$ARTIFACTS_DIR/openclaw-status.memory-core.txt"
