#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd npm
require_cmd node
require_cmd python3
ensure_common_dirs

OPENCLAW_DIR="$(guess_openclaw_install_dir || true)"
[[ -n "$OPENCLAW_DIR" ]] || die "could not locate global openclaw install dir; is openclaw installed via npm -g?"
EXT_DIR="$(guess_memory_lancedb_extension_dir "$OPENCLAW_DIR" || true)"
[[ -n "$EXT_DIR" ]] || die "could not locate memory-lancedb extension dir under $OPENCLAW_DIR"

DIST_PKG="$OPENCLAW_DIR/dist/package.json"
ROOT_PKG="$OPENCLAW_DIR/package.json"
[[ -f "$ROOT_PKG" ]] || die "missing root package.json: $ROOT_PKG"

if [[ ! -f "$DIST_PKG" ]]; then
  note "creating stub dist/package.json at $DIST_PKG"
  mkdir -p "$(dirname "$DIST_PKG")"
  python3 - <<PY
import json, pathlib
root_pkg = pathlib.Path(r'''$ROOT_PKG''')
dist_pkg = pathlib.Path(r'''$DIST_PKG''')
root = json.loads(root_pkg.read_text(encoding='utf-8'))
data = {
    'name': root.get('name', 'openclaw'),
    'version': root.get('version', 'unknown'),
    'dependencies': {'@lancedb/lancedb': '^0.27.1'},
}
dist_pkg.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
else
  note "patching $DIST_PKG to ensure @lancedb/lancedb is declared"
  python3 - <<PY
import json, pathlib
path = pathlib.Path(r'''$DIST_PKG''')
data = json.loads(path.read_text(encoding='utf-8'))
deps = data.setdefault('dependencies', {})
deps.setdefault('@lancedb/lancedb', '^0.27.1')
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PY
fi

note "installing @lancedb/lancedb into $EXT_DIR"
npm install --prefix "$EXT_DIR" @lancedb/lancedb

cat <<MSG

[READY]
Patched memory-lancedb runtime files.

Next steps:
1. ./scripts/configure_memory_lancedb.sh
2. openclaw gateway restart
3. ./scripts/diagnose_openclaw.sh
4. ./scripts/smoke_row2_lancedb.sh
MSG
