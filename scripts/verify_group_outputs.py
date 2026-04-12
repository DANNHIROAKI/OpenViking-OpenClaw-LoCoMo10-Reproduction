#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a group's merged answers / tokens / judge outputs")
    parser.add_argument("group", help="Group name, e.g. row1-memory-core")
    parser.add_argument("--root", default=".", help="Repo root (default: current directory)")
    parser.add_argument("--expected", type=int, default=1540, help="Expected merged answer count")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    group = args.group
    artifacts = root / "artifacts"
    runs_full = root / "runs" / "full" / group
    runs_smoke = root / "runs" / "smoke" / group

    report: dict[str, Any] = {
        "group": group,
        "smoke": {
            "ingest_exists": (runs_smoke / "ingest.txt").exists(),
            "qa_exists": (runs_smoke / "qa.txt").exists(),
            "qa_jsonl_exists": (runs_smoke / "qa.txt.1.jsonl").exists(),
        },
        "full": {
            "sample_dirs": sorted([p.name for p in runs_full.glob("sample_*") if p.is_dir()]),
            "qa_jsonl_count": len(list(runs_full.glob("sample_*/qa.txt.1.jsonl"))),
        },
        "artifacts": {},
        "checks": {},
    }

    answers_path = artifacts / f"{group}.answers.json"
    token_path = artifacts / f"{group}.token-summary.json"
    grades_path = artifacts / f"{group}.grades.json"

    answers_count = None
    if answers_path.exists():
        answers = load_json(answers_path)
        if isinstance(answers, list):
            answers_count = len(answers)

    token_total = None
    if token_path.exists():
        token_summary = load_json(token_path)
        if isinstance(token_summary, dict):
            token_total = token_summary.get("input_tokens_total")

    score = None
    if grades_path.exists():
        grades = load_json(grades_path)
        if isinstance(grades, dict):
            score = grades.get("score")

    report["artifacts"] = {
        "answers_path": str(answers_path),
        "answers_count": answers_count,
        "token_summary_path": str(token_path),
        "input_tokens_total": token_total,
        "grades_path": str(grades_path),
        "score": score,
    }

    checks = {
        "smoke_ready": all(report["smoke"].values()),
        "full_has_10_sample_dirs": len(report["full"]["sample_dirs"]) == 10,
        "full_has_10_qa_jsonl": report["full"]["qa_jsonl_count"] == 10,
        "answers_count_expected": answers_count == args.expected,
        "token_summary_present": isinstance(token_total, int),
        "judge_score_present": isinstance(score, (int, float)),
    }
    report["checks"] = checks
    report["ok"] = all(checks.values())

    out_path = artifacts / f"{group}.verification.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"written={out_path}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
