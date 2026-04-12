#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd openclaw
ensure_common_dirs

OUT="$ARTIFACTS_DIR/row4-probe.txt"
{
  echo "# row4 probe"
  echo "timestamp=$(date -Is)"
  echo
  echo "[openclaw version]"
  openclaw --version || true
  echo
  echo "[plugins.slots]"
  openclaw config get plugins.slots || true
  echo
  echo "[memory-openviking config]"
  openclaw config get plugins.entries.memory-openviking.config || true
  echo
  echo "[openclaw status]"
  openclaw status || true
  echo
  echo "[note]"
  echo "This script does not run row4 automatically. It only snapshots current OpenClaw plugin state for later manual investigation."
} > "$OUT" 2>&1

note "wrote $OUT"
cat "$OUT"
