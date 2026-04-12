from __future__ import annotations

import argparse
import os

from _common import ROOT, load_json, run_root, sha256_file, utc_now, write_json

JUDGE_PY = ROOT / 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge.py'
JUDGE_UTIL_PY = ROOT / 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge_util.py'



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('--mode', choices=['smoke', 'full'], required=True)
    parser.add_argument('--stage', default=None)
    args = parser.parse_args()

    root_path = run_root(args.mode, args.run_id, args.group, args.stage)
    run_spec = load_json(root_path / 'run_spec.json')
    payload = {
        'group': args.group,
        'run_id': args.run_id,
        'mode': args.mode,
        'stage': args.stage,
        'generated_at': utc_now(),
        'judge_model': os.environ.get('JUDGE_MODEL', 'gpt-4o-mini') or 'gpt-4o-mini',
        'judge_base_url': os.environ.get('JUDGE_BASE_URL') or None,
        'judge_api_key_supplied': bool(os.environ.get('JUDGE_API_KEY')),
        'judge_temperature': 0,
        'judge_response_protocol': 'json_via_prompt',
        'benchmark_artifact': run_spec.get('benchmark_path'),
        'judge_input_artifact': str((root_path / 'merged_answers.json').relative_to(ROOT)),
        'judge_output_artifact': str((root_path / 'grades.json').relative_to(ROOT)),
        'judge_snapshot_files': {
            'judge.py': {
                'path': 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge.py',
                'sha256': sha256_file(JUDGE_PY),
            },
            'judge_util.py': {
                'path': 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge_util.py',
                'sha256': sha256_file(JUDGE_UTIL_PY),
            },
        },
    }
    write_json(root_path / 'judge_run_spec.json', payload)
    print(f'Wrote {root_path / "judge_run_spec.json"}')


if __name__ == '__main__':
    main()
