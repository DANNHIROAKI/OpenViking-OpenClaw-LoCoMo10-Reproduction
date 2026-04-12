#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.env"
fi

: "${EVAL_REPO_URL:=https://github.com/ZaynJarvis/openclaw-eval.git}"
: "${EVAL_COMMIT:=75e07d696e0db5923ac767109f920df2fc807888}"
: "${OPENVIKING_REPO_URL:=https://github.com/volcengine/OpenViking.git}"
: "${OPENVIKING_REPO_REF:=main}"
: "${DATA_FILE:=data/openviking-locomo10-1540/locomo10_openviking_1540.json}"
: "${DATA_MANIFEST:=data/openviking-locomo10-1540/manifest.json}"
: "${OPENCLAW_VERSION:=2026.3.11}"
: "${OPENVIKING_VERSION:=0.1.18}"
: "${EVAL_PYTHON:=python3.13}"
: "${OV_PYTHON:=python3.10}"
: "${OPENCLAW_BASE_URL:=http://127.0.0.1:18789}"
: "${OPENVIKING_PLUGIN_MODE:=local}"
: "${JUDGE_MODEL:=gpt-4o-mini}"

THIRD_PARTY_DIR="$ROOT/third_party"
OPENCLAW_EVAL_DIR="$THIRD_PARTY_DIR/openclaw-eval"
OPENVIKING_SRC_DIR="$THIRD_PARTY_DIR/OpenViking"
EVAL_VENV_DIR="$OPENCLAW_EVAL_DIR/.venv"
OV_VENV_DIR="$ROOT/.venv-ov"
RUNS_DIR="$ROOT/runs"
SMOKE_RUNS_DIR="$RUNS_DIR/smoke"
FULL_RUNS_DIR="$RUNS_DIR/full"
ARTIFACTS_DIR="$ROOT/artifacts"
LOG_DIR="$ROOT/logs"
DATA_PATH="$ROOT/$DATA_FILE"
DATA_MANIFEST_PATH="$ROOT/$DATA_MANIFEST"

note() {
  printf '[INFO] %s\n' "$*"
}

warn() {
  printf '[WARN] %s\n' "$*" >&2
}

die() {
  printf '[ERROR] %s\n' "$*" >&2
  exit 1
}

ensure_dir() {
  mkdir -p "$1"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "command not found: $1"
}

require_file() {
  [[ -f "$1" ]] || die "missing file: $1"
}

require_dir() {
  [[ -d "$1" ]] || die "missing directory: $1"
}

require_env_var() {
  local name="$1"
  [[ -n "${!name:-}" ]] || die "environment variable not set: $name"
}

ensure_common_dirs() {
  ensure_dir "$THIRD_PARTY_DIR"
  ensure_dir "$SMOKE_RUNS_DIR"
  ensure_dir "$FULL_RUNS_DIR"
  ensure_dir "$ARTIFACTS_DIR"
  ensure_dir "$LOG_DIR"
}

ensure_eval_checkout() {
  require_dir "$OPENCLAW_EVAL_DIR"
  require_file "$OPENCLAW_EVAL_DIR/eval.py"
}

ensure_eval_venv() {
  require_file "$EVAL_VENV_DIR/bin/python"
}

ensure_ov_venv() {
  require_file "$OV_VENV_DIR/bin/python"
}

ensure_dataset() {
  require_file "$DATA_PATH"
  require_file "$DATA_MANIFEST_PATH"
}

print_repo_root() {
  printf '%s\n' "$ROOT"
}
