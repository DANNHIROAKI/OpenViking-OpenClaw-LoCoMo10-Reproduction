from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _common import (
    BENCHMARK_MANIFEST_PATH,
    PARALLEL,
    TAIL_LITERAL,
    get_claim_decision,
    get_group_spec,
    load_json,
    run_root,
    user_id,
    utc_now,
    write_json,
)

EXPECTED_SAMPLE_COUNTS = {
    ('full', None): 10,
    ('smoke', 'micro'): 1,
    ('smoke', 'extended'): 2,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _flag_values(cmd: list[str], flag: str) -> list[str]:
    values: list[str] = []
    for idx, item in enumerate(cmd):
        if item == flag and idx + 1 < len(cmd):
            values.append(cmd[idx + 1])
        elif item.startswith(f'{flag}='):
            values.append(item.split('=', 1)[1])
    return values


def _single_flag_value(cmd: list[str], flag: str) -> str | None:
    values = _flag_values(cmd, flag)
    if len(values) != 1:
        return None
    return values[0]


def _parallel_is_one(cmd: list[str]) -> bool:
    for i, item in enumerate(cmd):
        if item in {'-p', '--parallel'} and i + 1 < len(cmd):
            return cmd[i + 1] == '1'
        if item.startswith('--parallel='):
            return item.split('=', 1)[1] == '1'
    return False


def _expected_user(run_id: str, group: str, sample_idx: int) -> str:
    return user_id(run_id, group, sample_idx)


def _append_once(items: list[str], reason: str) -> None:
    if reason not in items:
        items.append(reason)


def _benchmark_manifest() -> dict[str, Any]:
    if not BENCHMARK_MANIFEST_PATH.exists():
        return {}
    return load_json(BENCHMARK_MANIFEST_PATH)


def _expected_result_count(mode: str, stage: str | None, run_spec: dict[str, Any]) -> int | None:
    manifest = _benchmark_manifest()
    counts = manifest.get('counts') or {}
    per_sample = manifest.get('per_sample') or []

    if mode == 'full':
        value = counts.get('filtered_total_qas')
        return int(value) if value is not None else 1540

    samples = run_spec.get('samples')
    qa_count = run_spec.get('qa_count')
    if isinstance(samples, list) and samples:
        if qa_count is not None:
            try:
                return len(samples) * int(qa_count)
            except Exception:
                pass
        total = 0
        try:
            for sample_idx in samples:
                total += int((per_sample[sample_idx] or {}).get('kept_cases') or 0)
            if total > 0:
                return total
        except Exception:
            pass

    if stage == 'micro':
        try:
            return int(qa_count) if qa_count is not None else 10
        except Exception:
            return 10
    if stage == 'extended':
        if len(per_sample) >= 2:
            return int((per_sample[0] or {}).get('kept_cases') or 0) + int((per_sample[1] or {}).get('kept_cases') or 0)
        return 233
    return None


def _expected_sample_count(mode: str, stage: str | None, run_spec: dict[str, Any]) -> int | None:
    samples = run_spec.get('samples')
    if isinstance(samples, list) and samples:
        return len(samples)
    return EXPECTED_SAMPLE_COUNTS.get((mode, None if mode == 'full' else stage))


def _config_block_has_actual_snapshot(block: dict[str, Any]) -> bool:
    return bool(block.get('actual_snapshot_public') or block.get('actual_snapshot'))


def summarize(group: str, run_id: str, mode: str, stage: str | None) -> Path:
    root_path = run_root(mode, run_id, group, stage)
    spec = get_group_spec(group)
    claim = get_claim_decision(group)
    run_spec = load_json(root_path / 'run_spec.json')
    run_meta = load_json(root_path / 'run_meta.json')
    config_snapshot = load_json(root_path / 'config_snapshot.json')
    config_drift = load_json(root_path / 'config_drift.json') if (root_path / 'config_drift.json').exists() else None

    ingest_total = 0
    qa_total = 0
    ingest_breakdown = []
    qa_breakdown = []
    merged_results = []
    qa_missing_usage = 0
    qa_zero_usage = 0
    qa_nonzero_usage = 0
    ingest_missing_usage = 0
    sample_count = 0

    for sample_meta in run_meta['samples']:
        sample_count += 1
        sroot = root_path / f"sample_{sample_meta['sample_idx']}"
        ingest_records = load_json(sroot / 'ingest.txt.json')
        qa_records = load_jsonl(sroot / 'qa_records.jsonl')
        for rec in ingest_records:
            usage = rec.get('usage') or {}
            if not usage:
                ingest_missing_usage += 1
            tokens = int(usage.get('input_tokens', 0) or 0)
            ingest_total += tokens
            ingest_breakdown.append({'sample_idx': sample_meta['sample_idx'], 'session': rec.get('session'), 'input_tokens': tokens})
        for rec in qa_records:
            usage = rec.get('usage') or {}
            if not usage:
                qa_missing_usage += 1
            tokens = int(usage.get('input_tokens', 0) or 0)
            if tokens == 0:
                qa_zero_usage += 1
            else:
                qa_nonzero_usage += 1
            qa_total += tokens
            qa_breakdown.append({'sample_idx': sample_meta['sample_idx'], 'qi': rec.get('qi'), 'input_tokens': tokens})
            merged_results.append(
                {
                    'sample_id': rec.get('sample_id'),
                    'sample_idx': sample_meta['sample_idx'],
                    'qi': rec.get('qi'),
                    'question': rec.get('question'),
                    'expected': rec.get('expected'),
                    'response': rec.get('response'),
                    'category': rec.get('category'),
                    'evidence': rec.get('evidence', []),
                    'usage': rec.get('usage', {}),
                }
            )

    write_json(root_path / 'merged_answers.json', {'results': merged_results, 'generated_at': utc_now()})
    write_json(
        root_path / 'ingest_token_summary.json',
        {
            'group': group,
            'run_id': run_id,
            'mode': mode,
            'stage': stage,
            'ingest_input_tokens_total': ingest_total,
            'breakdown': ingest_breakdown,
        },
    )
    write_json(
        root_path / 'qa_token_summary.json',
        {
            'group': group,
            'run_id': run_id,
            'mode': mode,
            'stage': stage,
            'qa_input_tokens_total': qa_total,
            'breakdown': qa_breakdown,
        },
    )
    write_json(
        root_path / 'pipeline_token_summary.json',
        {
            'group': group,
            'run_id': run_id,
            'mode': mode,
            'stage': stage,
            'visible_pipeline_input_tokens_total': ingest_total + qa_total,
            'ingest_input_tokens_total': ingest_total,
            'qa_input_tokens_total': qa_total,
        },
    )

    grades_path = root_path / 'grades.json'
    completion_rate = None
    completion_by_category = None
    if grades_path.exists():
        grades = load_json(grades_path)
        completion_rate = grades.get('score')
        cat: dict[str, dict[str, int]] = {}
        for item in grades.get('grades', []):
            key = str(item.get('category', 'unknown'))
            cat.setdefault(key, {'correct': 0, 'total': 0})
            cat[key]['total'] += 1
            if item.get('grade'):
                cat[key]['correct'] += 1
        completion_by_category = cat
        write_json(root_path / 'completion_by_category.json', completion_by_category)

    result_count = len(merged_results)
    expected_result_count = _expected_result_count(mode, stage, run_spec)
    expected_qas_valid = result_count == expected_result_count if expected_result_count is not None else result_count > 0

    expected_sample_count = _expected_sample_count(mode, stage, run_spec)
    sample_count_valid = sample_count == expected_sample_count if expected_sample_count is not None else True
    users_match = all(s['ingest_user'] == s['qa_user'] for s in run_meta['samples'])
    no_viking_flag = all('--viking' not in ' '.join(s['ingest_command']) and '--viking' not in ' '.join(s['qa_command']) for s in run_meta['samples'])
    parallel_valid = all(_parallel_is_one(s['qa_command']) for s in run_meta['samples'])

    invalidity_reasons: list[str] = []
    if not expected_qas_valid:
        invalidity_reasons.append(
            f'benchmark count mismatch: expected filtered QA count not satisfied (expected {expected_result_count}, got {result_count})'
        )
    if not sample_count_valid:
        invalidity_reasons.append(f'sample count mismatch: expected {expected_sample_count}, got {sample_count}')
    if not users_match:
        invalidity_reasons.append('ingest and qa used different user ids')
    if not no_viking_flag:
        invalidity_reasons.append('forbidden eval.py --viking flag detected')
    if not parallel_valid:
        invalidity_reasons.append('parallel != 1 in qa command')

    if run_spec.get('tail_literal') != TAIL_LITERAL:
        invalidity_reasons.append('run_spec tail literal drifted from frozen group definition')
    if run_spec.get('parallel') != PARALLEL:
        invalidity_reasons.append('run_spec parallel drifted from frozen group definition')
    if run_spec.get('gateway_only') is not True:
        invalidity_reasons.append('run_spec gateway_only flag missing or false')
    if run_spec.get('forbid_eval_viking_flag') is not True:
        invalidity_reasons.append('run_spec forbid_eval_viking_flag missing or false')

    for sample_meta in run_meta['samples']:
        sample_idx = sample_meta['sample_idx']
        expected_user = _expected_user(run_id, group, sample_idx)
        ingest_user_flag = _single_flag_value(sample_meta['ingest_command'], '--user')
        qa_user_flag = _single_flag_value(sample_meta['qa_command'], '--user')
        if not (
            sample_meta.get('ingest_user') == expected_user
            and sample_meta.get('qa_user') == expected_user
            and ingest_user_flag == expected_user
            and qa_user_flag == expected_user
        ):
            _append_once(invalidity_reasons, 'sample user id drifted from frozen user pattern')

        tail_values = _flag_values(sample_meta['ingest_command'], '--tail')
        if len(tail_values) != 1:
            _append_once(invalidity_reasons, 'ingest command missing required --tail')
        elif tail_values[0] != run_spec.get('tail_literal'):
            _append_once(invalidity_reasons, 'ingest command tail literal drifted from frozen spec')

    for cfg_name in ['openclaw', 'openviking']:
        if cfg_name == 'openviking' and spec.get('openviking_mode') is None:
            continue
        cfg_block = config_snapshot.get(cfg_name, {})
        if not _config_block_has_actual_snapshot(cfg_block):
            invalidity_reasons.append(f'{cfg_name} actual config snapshot missing')
            continue
        comparison = cfg_block.get('comparison') or {}
        if not comparison.get('actual_json_parsed'):
            invalidity_reasons.append(f'{cfg_name} actual config could not be parsed as JSON')
            continue
        if comparison.get('structural_subset_match') is not True:
            invalidity_reasons.append(f'{cfg_name} structural config mismatch vs frozen template')
        if comparison.get('exact_subset_match') is not True:
            invalidity_reasons.append(f'{cfg_name} exact config mismatch vs frozen template')

    runtime_arch = config_snapshot.get('runtime_architecture') or {}
    if runtime_arch.get('overall_passed') is not True:
        invalidity_reasons.append('runtime architecture proof failed or missing')
        if group == 'row3-openviking-minus-core':
            invalidity_reasons.append('row3 runtime did not prove legacy memory-slot path')
        if group == 'row4-compat-primary':
            invalidity_reasons.append('row4 runtime did not prove memory-core + contextEngine=openviking coexistence')

    if config_drift is None:
        invalidity_reasons.append('config_drift.json missing')
    elif config_drift.get('drift_detected'):
        invalidity_reasons.extend(config_drift.get('drift_reasons', []))

    if spec.get('openviking_mode') == 'local':
        if qa_total == 0:
            invalidity_reasons.append('OpenViking group produced qa_input_tokens_total == 0')
        if qa_zero_usage == result_count:
            invalidity_reasons.append('OpenViking group QA usage is all-zero across all records')
        if qa_missing_usage == result_count:
            invalidity_reasons.append('OpenViking group QA usage is missing across all records')

    if group == 'row2-memory-lancedb':
        runtime_audit = ((config_snapshot.get('runtime_audit_freeze') or {}).get(group) or {})
        if not runtime_audit.get('lancedb_embedding_provider'):
            invalidity_reasons.append('row2 runtime_audit_freeze missing lancedb_embedding_provider')

    pipeline_valid = len(invalidity_reasons) == 0
    notes = []
    if claim['effective_claim_class'] != claim['target_claim_class']:
        notes.append('effective claim class is more conservative than target claim class')
    if config_snapshot.get('plugin_inventory', {}).get('list_returncode') not in (0, None):
        notes.append('plugin inventory list command returned non-zero; inspect config snapshot artifacts manually')
    for item in config_snapshot.get('plugin_inventory', {}).get('inspect_outputs', []):
        if item.get('returncode') not in (0, None):
            notes.append(f"plugin inspect returned non-zero for {item['plugin_id']}")
    if qa_missing_usage > 0:
        notes.append(f'qa usage missing on {qa_missing_usage} records')
    if qa_zero_usage > 0:
        notes.append(f'qa usage zero on {qa_zero_usage} records')
    if ingest_missing_usage > 0:
        notes.append(f'ingest usage missing on {ingest_missing_usage} records')

    summary = {
        'group': group,
        'run_id': run_id,
        'mode': mode,
        'stage': stage,
        'claim_class': claim['effective_claim_class'],
        'target_claim_class': claim['target_claim_class'],
        'pipeline_status': 'valid' if pipeline_valid else 'invalid',
        'invalidity_reasons': invalidity_reasons,
        'completion_rate': completion_rate,
        'qa_input_tokens_total': qa_total,
        'ingest_input_tokens_total': ingest_total,
        'visible_pipeline_input_tokens_total': ingest_total + qa_total,
        'qa_usage_missing_count': qa_missing_usage,
        'qa_usage_zero_count': qa_zero_usage,
        'qa_usage_nonzero_count': qa_nonzero_usage,
        'result_count': result_count,
        'expected_result_count': expected_result_count,
        'sample_count': sample_count,
        'expected_sample_count': expected_sample_count,
        'snapshot_id': spec.get('openviking_snapshot_id') or 'openclaw-only',
        'runtime_architecture_status': 'passed' if runtime_arch.get('overall_passed') is True else 'failed',
        'selected_memory_slot': runtime_arch.get('selected_memory_slot'),
        'selected_context_engine_slot': runtime_arch.get('selected_context_engine_slot'),
        'runtime_architecture_blocking_reasons': runtime_arch.get('blocking_reasons', []),
        'notes': notes,
        'generated_at': utc_now(),
    }
    write_json(root_path / 'run_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return root_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('--mode', choices=['smoke', 'full'], required=True)
    parser.add_argument('--stage', default=None)
    args = parser.parse_args()
    summarize(args.group, args.run_id, args.mode, args.stage)


if __name__ == '__main__':
    main()
