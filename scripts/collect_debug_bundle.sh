#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

ensure_common_dirs
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$ARTIFACTS_DIR/debug-bundle-${STAMP}.tar.gz"

TMP_DIR="$ARTIFACTS_DIR/debug-bundle-${STAMP}"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

cp -a "$ROOT/docs" "$TMP_DIR/docs" 2>/dev/null || true
cp -a "$ROOT/logs" "$TMP_DIR/logs" 2>/dev/null || true
cp -a "$ROOT/runs/smoke" "$TMP_DIR/runs-smoke" 2>/dev/null || true
cp -a "$ROOT/artifacts" "$TMP_DIR/artifacts" 2>/dev/null || true
cp -a "$ROOT/.env.example" "$TMP_DIR/.env.example" 2>/dev/null || true

if command -v openclaw >/dev/null 2>&1; then
  openclaw --version > "$TMP_DIR/openclaw-version.txt" 2>&1 || true
  openclaw status > "$TMP_DIR/openclaw-status.txt" 2>&1 || true
  openclaw config get plugins.slots > "$TMP_DIR/openclaw-plugins-slots.txt" 2>&1 || true
fi

python3 "$ROOT/scripts/status_matrix.py" > "$TMP_DIR/status-matrix.txt" 2>&1 || true

tar -czf "$OUT" -C "$ARTIFACTS_DIR" "$(basename "$TMP_DIR")"
rm -rf "$TMP_DIR"

note "wrote $OUT"
