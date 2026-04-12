#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
RUNS = ROOT / "runs"


def exists(path: Path) -> bool:
    return path.exists()


def file_nonempty(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def load_json_if(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def env_loaded() -> bool:
    return (ROOT / ".env").exists()


def env_key_set(name: str) -> bool:
    # best-effort: only checks current shell inheritance when script is launched with exported vars
    return bool(os.environ.get(name))


def answers_count(group: str) -> int | None:
    path = ARTIFACTS / f"{group}.answers.json"
    data = load_json_if(path)
    if isinstance(data, list):
        return len(data)
    return None


def score_value(group: str):
    path = ARTIFACTS / f"{group}.grades.json"
    data = load_json_if(path)
    if isinstance(data, dict) and isinstance(data.get("score"), (int, float)):
        return data["score"]
    return None


def token_value(group: str):
    path = ARTIFACTS / f"{group}.token-summary.json"
    data = load_json_if(path)
    if isinstance(data, dict) and isinstance(data.get("input_tokens_total"), int):
        return data["input_tokens_total"]
    return None


def smoke_ok(group: str) -> bool:
    return file_nonempty(RUNS / "smoke" / group / "qa.txt") and file_nonempty(RUNS / "smoke" / group / "qa.txt.1.jsonl")


def full_started(group: str) -> bool:
    return (RUNS / "full" / group).exists()


def print_row(label: str, ok: bool, extra: str = "") -> None:
    icon = "[OK]" if ok else "[  ]"
    if extra:
        print(f"{icon} {label}: {extra}")
    else:
        print(f"{icon} {label}")


def next_step() -> str:
    if not env_loaded():
        return "cp .env.example .env"
    if not (ROOT / "third_party" / "openclaw-eval" / "eval.py").exists():
        return "./scripts/fetch_upstreams.sh"
    if not (ROOT / "third_party" / "openclaw-eval" / ".venv" / "bin" / "python").exists() or not (ROOT / ".venv-ov" / "bin" / "python").exists():
        return "./scripts/setup_envs.sh"
    if not file_nonempty(ARTIFACTS / "versions.txt"):
        return "openclaw onboard && ./scripts/record_versions.sh"
    if not smoke_ok("row1-memory-core"):
        return "./scripts/smoke_row1_memory_core.sh"
    if not (Path.home() / ".openclaw" / "openviking.env").exists():
        return "./scripts/install_openviking_helper.sh && ov-install"
    if not smoke_ok("row3-openviking-minus-core"):
        return "./scripts/smoke_row3_openviking_minus_core.sh"
    if answers_count("row1-memory-core") != 1540 or score_value("row1-memory-core") is None:
        return "./scripts/phase_b_full_core_and_ov.sh"
    if token_value("row2-memory-lancedb") is None and answers_count("row2-memory-lancedb") is None:
        return "./scripts/phase_c_row2.sh"
    return "python3 scripts/build_results_table.py"


def main() -> int:
    print("# Reproduction Status Matrix")
    print()
    print_row(".env exists", env_loaded())
    print_row("dataset manifest", file_nonempty(ROOT / "data" / "openviking-locomo10-1540" / "manifest.json"))
    print_row("official targets", file_nonempty(ROOT / "official_targets.json"))
    print_row("openclaw-eval checkout", exists(ROOT / "third_party" / "openclaw-eval" / "eval.py"))
    print_row("OpenViking checkout", exists(ROOT / "third_party" / "OpenViking"))
    print_row("eval venv", exists(ROOT / "third_party" / "openclaw-eval" / ".venv" / "bin" / "python"))
    print_row("OpenViking venv", exists(ROOT / ".venv-ov" / "bin" / "python"))
    print_row("versions artifact", file_nonempty(ARTIFACTS / "versions.txt"))
    print_row("OpenViking helper env", exists(Path.home() / ".openclaw" / "openviking.env"))
    print()

    for group in ["row1-memory-core", "row2-memory-lancedb", "row3-openviking-minus-core"]:
        count = answers_count(group)
        score = score_value(group)
        tokens = token_value(group)
        print_row(f"{group} smoke", smoke_ok(group))
        print_row(f"{group} full directory", full_started(group))
        print_row(f"{group} merged answers", count is not None, f"count={count}" if count is not None else "")
        print_row(f"{group} token summary", tokens is not None, f"input_tokens_total={tokens}" if tokens is not None else "")
        print_row(f"{group} judge result", score is not None, f"score={score:.4f}" if isinstance(score, (int, float)) else "")
        print()

    print("Next recommended command:")
    print(f"  {next_step()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
