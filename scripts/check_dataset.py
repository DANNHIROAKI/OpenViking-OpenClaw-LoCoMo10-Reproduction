#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "data" / "openviking-locomo10-1540" / "manifest.json"
JSON_PATH = ROOT / "data" / "openviking-locomo10-1540" / "locomo10_openviking_1540.json"
JSONL_PATH = ROOT / "data" / "openviking-locomo10-1540" / "locomo10_openviking_1540.jsonl"


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    jsonl_rows = [json.loads(line) for line in JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

    category_counter = Counter()
    total_after = 0
    category_5_present = False
    per_sample = []

    for item in data:
        qas = item.get("qa", [])
        total_after += len(qas)
        sample_counter = Counter(str(q.get("category", "")) for q in qas)
        category_counter.update(sample_counter)
        if "5" in sample_counter:
            category_5_present = True
        per_sample.append({
            "sample_id": item.get("sample_id"),
            "kept_cases": len(qas),
            "category_breakdown": dict(sorted(sample_counter.items(), key=lambda kv: kv[0])),
        })

    print(f"sample_count={len(data)}")
    print(f"total_after={total_after}")
    print(f"category_counts={dict(sorted(category_counter.items(), key=lambda kv: kv[0]))}")
    print(f"category_5_present={category_5_present}")
    print(f"jsonl_rows={len(jsonl_rows)}")
    print(f"manifest_total_after={manifest['stats']['total_cases_after_filter']}")

    expected_total = manifest["stats"]["total_cases_after_filter"]
    if total_after != expected_total:
        raise SystemExit(f"[ERROR] total_after mismatch: expected {expected_total}, got {total_after}")
    if len(jsonl_rows) != expected_total:
        raise SystemExit(f"[ERROR] jsonl row mismatch: expected {expected_total}, got {len(jsonl_rows)}")
    if category_5_present:
        raise SystemExit("[ERROR] category 5 still present in filtered dataset")

    manifest_per_sample = manifest["stats"]["per_sample"]
    if per_sample != manifest_per_sample:
        raise SystemExit("[ERROR] per-sample stats differ from manifest")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
