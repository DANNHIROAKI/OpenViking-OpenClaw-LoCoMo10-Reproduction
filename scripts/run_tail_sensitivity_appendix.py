from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from _common import (
    BENCHMARK_PATH,
    OPENCLAW_EVAL_DIR,
    PARALLEL,
    ROOT,
    TAIL_LITERAL,
    apply_env_file,
    ensure_dir,
    ensure_fresh_dir,
    get_group_spec,
    relpath,
    run_root,
    sha256_file,
    utc_now,
    write_json,
)
from capture_group_snapshot import capture_group_snapshot
from finalize_group import summarize as finalize_summarize
from run_eval_group import _current_config_state, _runtime_gate, _write_config_drift

VARIANTS = [
    {'stage': 'tail-empty', 'tail_literal': '[]'},
    {'stage': 'tail-frozen', 'tail_literal': TAIL_LITERAL},
]
SAMPLES = [0, 1]
REPORT_DIR = ROOT / 'reports/tail_sensitivity'



def appendix_storage_root(run_id: str, group: str, stage: str) -> Path:
    return ROOT / 'storage' / run_id / group / 'tail_sensitivity' / stage



def appendix_user_id(run_id: str, group: str, stage: str, sample_idx: int) -> str:
    return f'repro-{run_id}-{group}-{stage}-sample-{sample_idx}'



def _report_paths(group: str, run_id: str) -> tuple[Path, Path]:
    base = REPORT_DIR / f'{group}__{run_id}'
    return base.with_suffix('.csv'), base.with_suffix('.md')



def _pct(value: float | None) -> str:
    if value is None:
        return ''
    return f'{value:+.2%}'



def _pp(value: float | None) -> str:
    if value is None:
        return ''
    return f'{value:+.2f}pp'



def _run_variant(group: str, run_id: str, stage: str, tail_literal: str, required_paths: dict[str, Path]) -> Path:
    apply_env_file()
    spec = get_group_spec(group)
    base_url = os.environ['OPENCLAW_BASE_URL']
    token = os.environ['OPENCLAW_GATEWAY_TOKEN']
    eval_python = os.environ.get('EVAL_PYTHON', 'python3')

    root_path = run_root('smoke', run_id, group, stage)
    ensure_fresh_dir(root_path, f'appendix run root {stage}')

    storage = appendix_storage_root(run_id, group, stage)
    ensure_fresh_dir(storage, f'appendix storage root {stage}')
    ensure_dir(storage / 'cache')
    if spec['expected_storage'].get('lancedb'):
        ensure_dir(storage / 'lancedb')
    if spec['expected_storage'].get('openviking_workspace'):
        ensure_dir(storage / 'openviking-workspace')

    config_start = _current_config_state(group, required_paths)
    capture_group_snapshot(group, f'{run_id}-{stage}', root_path)

    run_spec = {
        'group': group,
        'run_id': run_id,
        'appendix': 'tail_sensitivity',
        'stage': stage,
        'mode': 'smoke',
        'samples': SAMPLES,
        'qa_count': None,
        'tail_literal': tail_literal,
        'parallel': PARALLEL,
        'benchmark_path': relpath(BENCHMARK_PATH),
        'openclaw_base_url': base_url,
        'gateway_only': True,
        'forbid_eval_viking_flag': True,
        'required_actual_configs': {key: str(path) for key, path in required_paths.items()},
        'created_at': utc_now(),
    }
    write_json(root_path / 'run_spec.json', run_spec)

    run_meta = {'samples': [], 'started_at': utc_now(), 'appendix': 'tail_sensitivity'}
    for sample_idx in SAMPLES:
        sroot = root_path / f'sample_{sample_idx}'
        ensure_fresh_dir(sroot, f'appendix sample root {sample_idx}')
        uid = appendix_user_id(run_id, group, stage, sample_idx)
        ingest_cmd = [
            eval_python, str(OPENCLAW_EVAL_DIR / 'eval.py'), 'ingest', str(BENCHMARK_PATH),
            '--base-url', base_url, '--token', token,
            '--sample', str(sample_idx), '--user', uid, '--tail', tail_literal,
            '--output', str(sroot / 'ingest.txt'),
        ]
        qa_cmd = [
            eval_python, str(OPENCLAW_EVAL_DIR / 'eval.py'), 'qa', str(BENCHMARK_PATH),
            '--base-url', base_url, '--token', token,
            '--sample', str(sample_idx), '--user', uid, '-p', str(PARALLEL),
            '--output', str(sroot / 'qa.txt'),
        ]

        ingest_cp = subprocess.run(ingest_cmd, text=True, capture_output=True)
        (sroot / 'ingest.console.log').write_text((ingest_cp.stdout or '') + '\n' + (ingest_cp.stderr or ''), encoding='utf-8')
        if ingest_cp.returncode != 0:
            raise SystemExit(f'appendix ingest failed for {group} {stage} sample {sample_idx}; see {relpath(sroot / "ingest.console.log")}')

        qa_cp = subprocess.run(qa_cmd, text=True, capture_output=True)
        (sroot / 'qa.console.log').write_text((qa_cp.stdout or '') + '\n' + (qa_cp.stderr or ''), encoding='utf-8')
        if qa_cp.returncode != 0:
            raise SystemExit(f'appendix qa failed for {group} {stage} sample {sample_idx}; see {relpath(sroot / "qa.console.log")}')

        candidates = sorted(sroot.glob('qa.txt.*.jsonl'))
        if len(candidates) != 1:
            raise SystemExit(f'expected exactly one qa.txt.*.jsonl under {sroot}, got {len(candidates)}')
        shutil.move(str(candidates[0]), str(sroot / 'qa_records.jsonl'))

        sample_meta = {
            'sample_idx': sample_idx,
            'user': uid,
            'ingest_user': uid,
            'qa_user': uid,
            'ingest_command': ingest_cmd,
            'qa_command': qa_cmd,
            'artifacts': {
                'ingest_text': relpath(sroot / 'ingest.txt'),
                'ingest_json': relpath(sroot / 'ingest.txt.json'),
                'qa_text': relpath(sroot / 'qa.txt'),
                'qa_records': relpath(sroot / 'qa_records.jsonl'),
            },
        }
        write_json(sroot / 'sample_run_meta.json', sample_meta)
        run_meta['samples'].append(sample_meta)

    run_meta['finished_at'] = utc_now()
    write_json(root_path / 'run_meta.json', run_meta)
    _write_config_drift(root_path, group, required_paths, config_start)
    finalize_summarize(group, run_id, 'smoke', stage)
    return root_path



def _write_report(group: str, run_id: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    summaries = {}
    for variant in VARIANTS:
        stage = variant['stage']
        root_path = run_root('smoke', run_id, group, stage)
        summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
        summaries[stage] = summary
        rows.append(
            {
                'group': group,
                'run_id': run_id,
                'stage': stage,
                'tail_literal': variant['tail_literal'],
                'completion_rate': summary.get('completion_rate'),
                'qa_input_tokens_total': summary.get('qa_input_tokens_total'),
                'ingest_input_tokens_total': summary.get('ingest_input_tokens_total'),
                'visible_pipeline_input_tokens_total': summary.get('visible_pipeline_input_tokens_total'),
                'pipeline_status': summary.get('pipeline_status'),
            }
        )

    empty = summaries['tail-empty']
    frozen = summaries['tail-frozen']
    diff_row = {
        'group': group,
        'run_id': run_id,
        'stage': 'diff:frozen-minus-empty',
        'tail_literal': '',
        'completion_rate': _pp(
            None if empty.get('completion_rate') is None or frozen.get('completion_rate') is None else (frozen['completion_rate'] - empty['completion_rate']) * 100
        ),
        'qa_input_tokens_total': _pct(
            None if empty.get('qa_input_tokens_total') in (None, 0) else (frozen['qa_input_tokens_total'] - empty['qa_input_tokens_total']) / empty['qa_input_tokens_total']
        ),
        'ingest_input_tokens_total': _pct(
            None if empty.get('ingest_input_tokens_total') in (None, 0) else (frozen['ingest_input_tokens_total'] - empty['ingest_input_tokens_total']) / empty['ingest_input_tokens_total']
        ),
        'visible_pipeline_input_tokens_total': _pct(
            None if empty.get('visible_pipeline_input_tokens_total') in (None, 0) else (frozen['visible_pipeline_input_tokens_total'] - empty['visible_pipeline_input_tokens_total']) / empty['visible_pipeline_input_tokens_total']
        ),
        'pipeline_status': f"{empty.get('pipeline_status')} -> {frozen.get('pipeline_status')}",
    }
    rows.append(diff_row)

    csv_path, md_path = _report_paths(group, run_id)
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    md_lines = [
        '# Tail Sensitivity Appendix',
        '',
        '> Auto-generated by `python3 scripts/run_tail_sensitivity_appendix.py`.',
        '',
        '| stage | tail_literal | pipeline_status | completion_rate / delta | qa_input_tokens_total / delta | ingest_input_tokens_total / delta | visible_pipeline_input_tokens_total / delta |',
        '|---|---|---|---:|---:|---:|---:|',
    ]
    for row in rows:
        md_lines.append('| {stage} | {tail_literal} | {pipeline_status} | {completion_rate} | {qa_input_tokens_total} | {ingest_input_tokens_total} | {visible_pipeline_input_tokens_total} |'.format(**row))
    md_path.write_text('\n'.join(md_lines) + '\n', encoding='utf-8')
    print(f'Wrote {csv_path} and {md_path}')



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    args = parser.parse_args()
    required_paths = _runtime_gate(args.group)
    for variant in VARIANTS:
        _run_variant(args.group, args.run_id, variant['stage'], variant['tail_literal'], required_paths)
    _write_report(args.group, args.run_id)


if __name__ == '__main__':
    main()
