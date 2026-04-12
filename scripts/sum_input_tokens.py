#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import re
from pathlib import Path

PATTERN = re.compile(r"^input_tokens:\s*(\d+)\s*$")


def parse_input_tokens(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = PATTERN.match(line.strip())
            if m:
                return int(m.group(1))
    raise ValueError(f"input_tokens not found in {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sum input_tokens across qa.txt files")
    parser.add_argument("group", help="Group name, e.g. row1-memory-core")
    parser.add_argument("--root", default=".", help="Repo root (default: current directory)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    pattern = str(root / "runs" / "full" / args.group / "sample_*" / "qa.txt")
    paths = sorted(glob.glob(pattern))
    if not paths:
        raise SystemExit(f"[ERROR] no files matched: {pattern}")

    per_file: dict[str, int] = {}
    total = 0
    for path in paths:
        value = parse_input_tokens(path)
        per_file[path] = value
        total += value

    summary = {
        "group": args.group,
        "sample_count": len(paths),
        "input_tokens_total": total,
        "files": per_file,
    }

    out_path = root / "artifacts" / f"{args.group}.token-summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"written={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
