#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd openclaw
ensure_common_dirs

ENV_FILE="$HOME/.openclaw/openviking.env"
[[ -f "$ENV_FILE" ]] || die "missing $ENV_FILE ; run ov-install first"

# shellcheck disable=SC1090
source "$ENV_FILE"

OV_CONFIG_PATH="${OPENVIKING_CONFIG_FILE:-$HOME/.openviking/ov.conf}"
OV_PORT="${OPENVIKING_PORT:-1933}"
OV_TARGET_URI="${OPENVIKING_TARGET_URI:-viking://user/default/memories}"

note "configuring OpenClaw to use memory-openviking ($OPENVIKING_PLUGIN_MODE mode)"
openclaw config set plugins.enabled true --json
openclaw config set plugins.slots.memory memory-openviking
openclaw config set plugins.entries.memory-openviking.config.mode "$OPENVIKING_PLUGIN_MODE"
openclaw config set plugins.entries.memory-openviking.config.targetUri "$OV_TARGET_URI" || true
openclaw config set plugins.entries.memory-openviking.config.autoRecall true --json
openclaw config set plugins.entries.memory-openviking.config.autoCapture true --json

if [[ "$OPENVIKING_PLUGIN_MODE" == "local" ]]; then
  openclaw config set plugins.entries.memory-openviking.config.configPath "$OV_CONFIG_PATH" || true
  openclaw config set plugins.entries.memory-openviking.config.port "$OV_PORT" || true
fi

if [[ "$OPENVIKING_PLUGIN_MODE" == "remote" ]]; then
  require_env_var OPENVIKING_BASE_URL
  openclaw config set plugins.entries.memory-openviking.config.baseUrl "$OPENVIKING_BASE_URL"
  if [[ -n "${OPENVIKING_API_KEY:-}" ]]; then
    openclaw config set plugins.entries.memory-openviking.config.apiKey "$OPENVIKING_API_KEY"
  fi
fi

openclaw gateway restart
openclaw status | tee "$ARTIFACTS_DIR/openclaw-status.memory-openviking.txt"
