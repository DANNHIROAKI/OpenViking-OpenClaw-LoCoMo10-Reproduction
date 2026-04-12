from __future__ import annotations

import argparse

from _common import load_json, run_root

BASE_REQUIRED_GROUP_FILES = [
    'run_spec.json',
    'run_meta.json',
    'config_snapshot.json',
    'config_drift.json',
    'merged_answers.json',
    'qa_token_summary.json',
    'ingest_token_summary.json',
    'pipeline_token_summary.json',
    'run_summary.json',
]
JUDGE_REQUIRED_GROUP_FILES = [
    'judge_run_spec.json',
    'grades.json',
]
REQUIRED_SAMPLE_FILES = [
    'ingest.txt',
    'ingest.txt.json',
    'qa.txt',
    'qa_records.jsonl',
    'ingest.console.log',
    'qa.console.log',
    'sample_run_meta.json',
]



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('--mode', choices=['smoke', 'full'], required=True)
    parser.add_argument('--stage', default=None)
    parser.add_argument('--require-judge', action='store_true')
    args = parser.parse_args()
    root_path = run_root(args.mode, args.run_id, args.group, args.stage)
    missing = []
    required_group_files = list(BASE_REQUIRED_GROUP_FILES)
    if args.require_judge:
        required_group_files.extend(JUDGE_REQUIRED_GROUP_FILES)
    for name in required_group_files:
        if not (root_path / name).exists():
            missing.append(str(root_path / name))
    for sroot in sorted(root_path.glob('sample_*')):
        for name in REQUIRED_SAMPLE_FILES:
            if not (sroot / name).exists():
                missing.append(str(sroot / name))
    if missing:
        print('Missing files:')
        for item in missing:
            print(f'  - {item}')
        raise SystemExit(1)
    summary = load_json(root_path / 'run_summary.json')
    print(summary['pipeline_status'])
    if summary.get('invalidity_reasons'):
        print('invalidity_reasons:')
        for reason in summary['invalidity_reasons']:
            print(f'  - {reason}')
    print(f'verified: {root_path}')


if __name__ == '__main__':
    main()
