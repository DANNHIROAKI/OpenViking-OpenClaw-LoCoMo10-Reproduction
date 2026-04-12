#!/usr/bin/env bash
set -Eeuo pipefail
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd git
ensure_common_dirs

clone_or_update() {
  local url="$1"
  local dir="$2"
  local checkout_ref="$3"

  if [[ ! -d "$dir/.git" ]]; then
    note "cloning $url -> $dir"
    git clone "$url" "$dir"
  else
    note "updating $dir"
    git -C "$dir" fetch --all --tags --prune
  fi

  note "checking out $checkout_ref in $dir"
  git -C "$dir" checkout "$checkout_ref"
}

clone_or_update "$EVAL_REPO_URL" "$OPENCLAW_EVAL_DIR" "$EVAL_COMMIT"
clone_or_update "$OPENVIKING_REPO_URL" "$OPENVIKING_SRC_DIR" "$OPENVIKING_REPO_REF"

note "done"
note "openclaw-eval HEAD: $(git -C "$OPENCLAW_EVAL_DIR" rev-parse HEAD)"
note "OpenViking HEAD: $(git -C "$OPENVIKING_SRC_DIR" rev-parse HEAD)"
