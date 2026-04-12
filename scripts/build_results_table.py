#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TARGETS_PATH = ROOT / "official_targets.json"
ARTIFACTS_DIR = ROOT / "artifacts"


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pct_or_empty(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2%}"


def int_or_empty(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value:,}"


def maybe_number(value: Any) -> float | int | None:
    if isinstance(value, (int, float)):
        return value
    return None


def main() -> int:
    targets = load_json(TARGETS_PATH)
    if targets is None:
        raise SystemExit(f"[ERROR] missing {TARGETS_PATH}")

    groups = targets["groups"]
    rows: list[dict[str, Any]] = []

    for group_id, target in groups.items():
        answers = load_json(ARTIFACTS_DIR / f"{group_id}.answers.json")
        grades = load_json(ARTIFACTS_DIR / f"{group_id}.grades.json")
        token_summary = load_json(ARTIFACTS_DIR / f"{group_id}.token-summary.json")

        actual_score = None
        if isinstance(grades, dict):
            actual_score = maybe_number(grades.get("score"))

        actual_input_tokens = None
        if isinstance(token_summary, dict):
            token_value = token_summary.get("input_tokens_total")
            if isinstance(token_value, int):
                actual_input_tokens = token_value

        merged_count = None
        if isinstance(answers, list):
            merged_count = len(answers)

        row = {
            "group_id": group_id,
            "group_label": target["label"],
            "target_task_completion_rate": target["target_task_completion_rate"],
            "actual_task_completion_rate": actual_score,
            "target_input_tokens_total": target["target_input_tokens_total"],
            "actual_input_tokens_total": actual_input_tokens,
            "answers_merged": merged_count,
            "score_delta": None if actual_score is None else actual_score - target["target_task_completion_rate"],
            "input_tokens_delta": None if actual_input_tokens is None else actual_input_tokens - target["target_input_tokens_total"],
            "status": "done" if actual_score is not None and actual_input_tokens is not None else "pending",
        }
        rows.append(row)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = ARTIFACTS_DIR / "results-summary.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    csv_path = ARTIFACTS_DIR / "results-summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "group_id",
                "group_label",
                "target_task_completion_rate",
                "actual_task_completion_rate",
                "target_input_tokens_total",
                "actual_input_tokens_total",
                "answers_merged",
                "score_delta",
                "input_tokens_delta",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    md_path = ARTIFACTS_DIR / "results-summary.md"
    lines = [
        "# Results Summary",
        "",
        "| Group | Official task completion | Your task completion | Official input tokens | Your input tokens | Merged answers | Status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {label} | {target_score} | {actual_score} | {target_tokens} | {actual_tokens} | {answers} | {status} |".format(
                label=row["group_label"],
                target_score=pct_or_empty(row["target_task_completion_rate"]),
                actual_score=pct_or_empty(row["actual_task_completion_rate"]),
                target_tokens=int_or_empty(row["target_input_tokens_total"]),
                actual_tokens=int_or_empty(row["actual_input_tokens_total"]),
                answers=row["answers_merged"] if row["answers_merged"] is not None else "",
                status=row["status"],
            )
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"written={json_path}")
    print(f"written={csv_path}")
    print(f"written={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
