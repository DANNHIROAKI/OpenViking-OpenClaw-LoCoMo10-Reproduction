#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge qa.txt.1.jsonl files into one answers.json")
    parser.add_argument("group", help="Group name, e.g. row1-memory-core")
    parser.add_argument("--root", default=".", help="Repo root (default: current directory)")
    parser.add_argument("--expected", type=int, default=None, help="Expected merged record count")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    run_dir = root / "runs" / "full" / args.group
    out_dir = root / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = str(run_dir / "sample_*" / "qa.txt.1.jsonl")
    paths = sorted(glob.glob(pattern))
    if not paths:
        raise SystemExit(f"[ERROR] no files matched: {pattern}")

    records: list[dict] = []
    for path in paths:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

    out_path = out_dir / f"{args.group}.answers.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"merged={len(records)}")
    print(f"written={out_path}")

    if args.expected is not None and len(records) != args.expected:
        raise SystemExit(
            f"[ERROR] merged count mismatch: expected {args.expected}, got {len(records)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
