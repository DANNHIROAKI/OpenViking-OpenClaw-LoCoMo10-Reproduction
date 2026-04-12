#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ROOT/.env"
  set +a
fi
if [[ -n "${REPRO_RUNTIME_ENV_FILE:-}" && -f "${REPRO_RUNTIME_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${REPRO_RUNTIME_ENV_FILE}"
  set +a
fi
note() { printf '[INFO] %s\n' "$*"; }
die() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

require_runtime_env() {
  [[ -n "${REPRO_RUNTIME_ENV_FILE:-}" ]] || die "missing REPRO_RUNTIME_ENV_FILE"
  [[ -f "${REPRO_RUNTIME_ENV_FILE}" ]] || die "runtime env file not found: ${REPRO_RUNTIME_ENV_FILE}"
  [[ -n "${OPENCLAW_CONFIG_PATH:-}" ]] || die "missing OPENCLAW_CONFIG_PATH"
  [[ -f "${OPENCLAW_CONFIG_PATH}" ]] || die "OPENCLAW_CONFIG_PATH not found: ${OPENCLAW_CONFIG_PATH}"
}
