from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from _common import ROOT, load_json

OUT_DIR = ROOT / 'reports/manual_audit_samples'
DEFAULT_COUNT = 100
DEFAULT_SEED = 20260412



def latest_valid_run(group: str) -> tuple[str, Path] | None:
    candidates = sorted(ROOT.glob(f'runs/full/*/{group}/run_summary.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates:
        data = load_json(path)
        if data.get('pipeline_status') == 'valid':
            return data['run_id'], path.parent
    return None



def resolve_run(group: str, run_id: str | None) -> tuple[str, Path]:
    if run_id:
        root = ROOT / 'runs/full' / run_id / group
        if not root.exists():
            raise SystemExit(f'run not found: {root}')
        summary = load_json(root / 'run_summary.json')
        if summary.get('pipeline_status') != 'valid':
            raise SystemExit(f'run is not valid: {root}')
        return run_id, root
    latest = latest_valid_run(group)
    if latest is None:
        raise SystemExit(f'no valid full run found for {group}')
    return latest



def normalize_bool(value: Any) -> str:
    if value is True:
        return 'correct'
    if value is False:
        return 'wrong'
    return ''



def build_quotas(items: list[dict[str, Any]], total: int) -> dict[str, int]:
    by_cat = Counter(str(item.get('category', 'unknown')) for item in items)
    raw = {cat: (count / len(items)) * total for cat, count in by_cat.items()}
    quotas = {cat: int(math.floor(val)) for cat, val in raw.items()}
    allocated = sum(quotas.values())
    remainder = total - allocated
    ranked = sorted(raw.items(), key=lambda kv: (kv[1] - math.floor(kv[1]), kv[0]), reverse=True)
    idx = 0
    while remainder > 0 and ranked:
        cat = ranked[idx % len(ranked)][0]
        quotas[cat] += 1
        remainder -= 1
        idx += 1
    for cat, count in by_cat.items():
        if count > 0 and quotas.get(cat, 0) == 0 and total >= len(by_cat):
            quotas[cat] = 1
    overflow = sum(quotas.values()) - total
    if overflow > 0:
        for cat, _ in sorted(quotas.items(), key=lambda kv: kv[1], reverse=True):
            if overflow == 0:
                break
            if quotas[cat] > 1:
                quotas[cat] -= 1
                overflow -= 1
    return quotas



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--count', type=int, default=DEFAULT_COUNT)
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    run_id, run_root = resolve_run(args.group, args.run_id)
    merged = load_json(run_root / 'merged_answers.json')['results']
    grades = load_json(run_root / 'grades.json')['grades']
    grade_map = {(item.get('sample_id'), int(item.get('qi'))): item for item in grades}

    enriched = []
    for item in merged:
        key = (item.get('sample_id'), int(item.get('qi')))
        grade = grade_map.get(key, {})
        enriched.append(
            {
                'group': args.group,
                'run_id': run_id,
                'sample_id': item.get('sample_id'),
                'sample_idx': item.get('sample_idx'),
                'qi': item.get('qi'),
                'category': item.get('category'),
                'question': item.get('question'),
                'gold': item.get('expected'),
                'response': item.get('response'),
                'judge_result': normalize_bool(grade.get('grade')),
                'human_result': '',
                'disagreement_reason': '',
            }
        )

    if len(enriched) < args.count:
        raise SystemExit(f'requested {args.count} audit cases but run only has {len(enriched)} answers')

    quotas = build_quotas(enriched, args.count)
    rng = random.Random(args.seed)
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in enriched:
        by_cat[str(item['category'])].append(item)
    for bucket in by_cat.values():
        rng.shuffle(bucket)

    selected: list[dict[str, Any]] = []
    for cat, quota in sorted(quotas.items(), key=lambda kv: kv[0]):
        bucket = by_cat.get(cat, [])
        selected.extend(bucket[: min(quota, len(bucket))])

    if len(selected) < args.count:
        leftovers = [item for item in enriched if (item['sample_id'], item['qi']) not in {(s['sample_id'], s['qi']) for s in selected}]
        rng.shuffle(leftovers)
        selected.extend(leftovers[: args.count - len(selected)])

    selected = sorted(selected[: args.count], key=lambda item: (str(item['category']), item['sample_id'], int(item['qi'])))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / f'{args.group}__{run_id}.csv'
    manifest_path = OUT_DIR / f'{args.group}__{run_id}.manifest.json'

    with csv_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'group', 'run_id', 'sample_id', 'sample_idx', 'qi', 'category', 'question', 'gold', 'response',
                'judge_result', 'human_result', 'disagreement_reason',
            ],
        )
        writer.writeheader()
        writer.writerows(selected)

    manifest = {
        'group': args.group,
        'run_id': run_id,
        'count': args.count,
        'seed': args.seed,
        'source_run_root': str(run_root.relative_to(ROOT)),
        'quotas': quotas,
        'output_csv': str(csv_path.relative_to(ROOT)),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Wrote {csv_path} and {manifest_path}')


if __name__ == '__main__':
    main()
