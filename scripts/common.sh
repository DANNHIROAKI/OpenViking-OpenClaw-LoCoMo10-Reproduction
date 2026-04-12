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
