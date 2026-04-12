from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import requests

from _common import (
    BENCHMARK_MANIFEST_PATH,
    BENCHMARK_PATH,
    OPENCLAW_EVAL_DIR,
    PARALLEL,
    ROOT,
    TAIL_LITERAL,
    collect_env_placeholders,
    ensure_dir,
    ensure_fresh_dir,
    get_claim_decision,
    get_group_spec,
    group_readiness,
    load_json,
    merged_env,
    path_label,
    relpath,
    render_placeholders,
    run_root,
    sample_root,
    sha256_file,
    storage_root,
    user_id,
    utc_now,
    write_json,
)
from capture_group_snapshot import capture_group_snapshot

OPENCLAW_TEMPLATES = ROOT / 'env/openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env/openviking_config_templates'
VERSIONS_MANIFEST = ROOT / 'env/versions_manifest.json'

STAGE_PRESETS = {
    'micro': {'mode': 'smoke', 'samples': [0], 'qa_count': 10},
    'extended': {'mode': 'smoke', 'samples': [0, 1], 'qa_count': None},
    'full': {'mode': 'full', 'samples': list(range(10)), 'qa_count': None},
}

PROBE_FACTS = [
    ('shell', 'fish'),
    ('folder-color', 'blue'),
    ('probe-codename', 'glacier-pine'),
]
PROBE_QUESTIONS = [
    ('What shell do I prefer for one-off scripts?', 'fish'),
    ('What color is my LoCoMo scratch folder?', 'blue'),
    ('What is the codename for this probe?', 'glacier-pine'),
]


def gateway_send(base_url: str, token: str, user: str, message: str) -> tuple[str, dict[str, Any]]:
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    payload = {'model': 'openclaw', 'input': message, 'stream': False, 'user': user}
    resp = requests.post(f'{base_url}/v1/responses', json=payload, headers=headers, timeout=300)
    resp.raise_for_status()
    body = resp.json()
    text_parts = []
    for item in body.get('output', []):
        if item.get('type') == 'message':
            for content in item.get('content', []):
                if content.get('type') == 'output_text':
                    text_parts.append(content.get('text', ''))
    return '\n'.join(text_parts).strip(), body.get('usage', {})


def _template_paths_for_group(group: str) -> list[Path]:
    paths = []
    oc = OPENCLAW_TEMPLATES / f'{group}.json'
    ov = OPENVIKING_TEMPLATES / f'{group}.local.json'
    if oc.exists():
        paths.append(oc)
    if ov.exists():
        paths.append(ov)
    return paths


def _assert_versions_manifest_ready_for_group(group: str) -> None:
    if not VERSIONS_MANIFEST.exists():
        raise SystemExit('missing env/versions_manifest.json; run python3 scripts/freeze_versions.py')
    manifest = load_json(VERSIONS_MANIFEST)
    if manifest.get('capture_status') != 'captured':
        raise SystemExit('env/versions_manifest.json is not captured; run python3 scripts/freeze_versions.py')
    readiness = group_readiness(group, manifest)
    if not readiness:
        raise SystemExit(f'env/versions_manifest.json is missing group_readiness for {group}; rerun python3 scripts/freeze_versions.py')
    if not readiness.get('ready_for_formal_wrapper'):
        reasons = readiness.get('blocking_reasons') or ['unknown readiness failure']
        raise SystemExit(f'{group} is not ready for the formal wrapper per env/versions_manifest.json: ' + '; '.join(reasons))


def _assert_benchmark_ready() -> None:
    if not BENCHMARK_MANIFEST_PATH.exists():
        raise SystemExit('missing benchmark/manifest.json; run python3 scripts/build_benchmark.py')
    manifest = load_json(BENCHMARK_MANIFEST_PATH)
    if manifest.get('counts', {}).get('filtered_total_qas') != 1540:
        raise SystemExit('benchmark/manifest.json does not certify 1540 filtered QA cases')
    if manifest.get('counts', {}).get('raw_total_qas') != 1986:
        raise SystemExit('benchmark/manifest.json does not certify 1986 raw QA cases')


def _assert_template_env_ready(group: str) -> None:
    env = merged_env()
    mapping = {'run_id': 'runtime-check', 'group': group}
    missing_messages = []
    for path in _template_paths_for_group(group):
        template = load_json(path)
        missing = sorted(var for var in collect_env_placeholders(template) if env.get(var) in (None, ''))
        if missing:
            missing_messages.append(f'{relpath(path)} missing env vars: {missing}')
            continue
        try:
            render_placeholders(template, mapping, expand_env=True, env=env, strict_env=True)
        except Exception as exc:
            missing_messages.append(f'{relpath(path)} could not be fully materialized: {exc}')
    if missing_messages:
        raise SystemExit('; '.join(missing_messages))


def _required_config_paths(group: str) -> dict[str, Path]:
    env = merged_env()
    spec = get_group_spec(group)
    required: dict[str, Path] = {}
    for env_name in spec.get('required_actual_configs', []):
        raw = env.get(env_name)
        if not raw:
            raise SystemExit(f'{group} requires env var {env_name} for formal config snapshot capture')
        path = Path(raw).expanduser()
        if not path.exists():
            raise SystemExit(f'{group} required config file does not exist: {env_name} -> {path}')
        required[env_name] = path
    if spec.get('require_openviking_health') and not env.get('OPENVIKING_HEALTH_URL'):
        raise SystemExit(f'{group} requires OPENVIKING_HEALTH_URL for probe/health capture')
    return required


def _current_config_state(group: str, required_paths: dict[str, Path]) -> dict[str, Any]:
    state: dict[str, Any] = {'captured_at': utc_now(), 'group': group, 'paths': {}}
    for env_name, path in required_paths.items():
        state['paths'][env_name] = {'path': str(path), 'sha256': sha256_file(path)}
    return state


def _write_config_drift(root_path: Path, group: str, required_paths: dict[str, Path], start_state: dict[str, Any]) -> None:
    end_state = _current_config_state(group, required_paths)
    start_paths = start_state.get('paths', {})
    end_paths = end_state.get('paths', {})
    drift_reasons = []
    for env_name, start_item in start_paths.items():
        end_item = end_paths.get(env_name)
        if end_item is None:
            drift_reasons.append(f'{env_name}: end-state snapshot missing')
            continue
        if start_item.get('sha256') != end_item.get('sha256'):
            drift_reasons.append(f'{env_name}: sha256 changed during run')
    write_json(
        root_path / 'config_drift.json',
        {
            'group': group,
            'checked_at': utc_now(),
            'start': start_state,
            'end': end_state,
            'drift_detected': len(drift_reasons) > 0,
            'drift_reasons': drift_reasons,
        },
    )


def _runtime_gate(group: str) -> dict[str, Path]:
    spec = get_group_spec(group)
    if spec.get('manual_only'):
        raise SystemExit(f'{group} is appendix/manual-only and cannot be executed by the mainline wrapper')
    _assert_versions_manifest_ready_for_group(group)
    _assert_benchmark_ready()
    _assert_template_env_ready(group)
    env = merged_env()
    if not env.get('OPENCLAW_BASE_URL'):
        raise SystemExit('missing OPENCLAW_BASE_URL for formal gateway runs')
    if not env.get('OPENCLAW_GATEWAY_TOKEN'):
        raise SystemExit('missing OPENCLAW_GATEWAY_TOKEN for formal gateway runs')
    return _required_config_paths(group)


def _qa_usage_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    missing = 0
    zero = 0
    nonzero = 0
    for rec in records:
        usage = rec.get('usage') or {}
        if not usage:
            missing += 1
        tokens = int(usage.get('input_tokens', 0) or 0)
        if tokens == 0:
            zero += 1
        else:
            nonzero += 1
    return {
        'qa_usage_missing_count': missing,
        'qa_usage_zero_count': zero,
        'qa_usage_nonzero_count': nonzero,
    }


def _log_baseline(log_file: str | None) -> dict[str, Any] | None:
    if not log_file:
        return None
    path = Path(log_file)
    if not path.exists():
        return {'path': str(path), 'exists': False, 'size': 0, 'inode': None, 'mtime_ns': None}
    stat = path.stat()
    return {'path': str(path), 'exists': True, 'size': stat.st_size, 'inode': stat.st_ino, 'mtime_ns': stat.st_mtime_ns}


def _read_log_delta(baseline: dict[str, Any] | None) -> dict[str, Any] | None:
    if baseline is None:
        return None
    path = Path(baseline['path'])
    if not path.exists():
        return {'path': str(path), 'delta_bytes': 0, 'capture_like': False, 'recall_like': False, 'exists_after_probe': False}

    stat = path.stat()
    start_size = int(baseline.get('size') or 0)
    same_inode = baseline.get('inode') == stat.st_ino and baseline.get('exists') is True
    read_from = start_size if same_inode and stat.st_size >= start_size else 0
    with path.open('rb') as f:
        f.seek(read_from)
        delta_bytes = f.read()
    text = delta_bytes.decode('utf-8', errors='ignore')
    lowered = text.lower()
    return {
        'path': str(path),
        'exists_after_probe': True,
        'delta_bytes': len(delta_bytes),
        'capture_like': 'capture' in lowered,
        'recall_like': 'recall' in lowered,
        'delta_excerpt': text[-4000:],
        'same_inode_as_baseline': same_inode,
        'read_from_byte': read_from,
    }


def _health_status(url: str | None) -> dict[str, Any] | None:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=10)
        return {'url': url, 'status_code': r.status_code, 'body': r.text[:1000], 'passed': 200 <= r.status_code < 300}
    except Exception as exc:
        return {'url': url, 'error': str(exc), 'passed': False}


def _build_probe_gate_checks(
    *,
    group: str,
    spec: dict[str, Any],
    correct: int,
    usage_counts: dict[str, int],
    runtime_arch: dict[str, Any],
    health_result: dict[str, Any] | None,
    log_trace: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, Any]], list[str], bool]:
    gate_checks: dict[str, dict[str, Any]] = {
        'memory_recall_accuracy': {
            'passed': correct >= 2,
            'observed_correct': correct,
            'required_min': 2,
        },
        'qa_usage_nonzero': {
            'passed': usage_counts['qa_usage_nonzero_count'] == len(PROBE_QUESTIONS),
            'nonzero_count': usage_counts['qa_usage_nonzero_count'],
            'zero_count': usage_counts['qa_usage_zero_count'],
            'missing_count': usage_counts['qa_usage_missing_count'],
            'total': len(PROBE_QUESTIONS),
        },
        'runtime_architecture': {
            'passed': runtime_arch.get('overall_passed') is True,
            'blocking_reasons': runtime_arch.get('blocking_reasons', []),
        },
        'openviking_health': {
            'passed': (health_result or {}).get('passed', True),
            'required': bool(spec.get('require_openviking_health')),
            'status_code': (health_result or {}).get('status_code'),
            'error': (health_result or {}).get('error'),
        },
        'openviking_log_capture_like': {
            'passed': bool((log_trace or {}).get('capture_like')) if spec.get('require_openviking_health') else True,
            'required': bool(spec.get('require_openviking_health')),
        },
        'openviking_log_recall_like': {
            'passed': bool((log_trace or {}).get('recall_like')) if spec.get('require_openviking_health') else True,
            'required': bool(spec.get('require_openviking_health')),
        },
    }
    if group == 'row4-compat-primary':
        gate_checks['row4_coexistence_proved'] = {
            'passed': runtime_arch.get('checks', {}).get('row4_coexistence_proved') is True,
            'required': True,
        }

    required_gate_names = ['memory_recall_accuracy', 'qa_usage_nonzero', 'runtime_architecture']
    if spec.get('require_openviking_health'):
        required_gate_names.extend(['openviking_health', 'openviking_log_capture_like', 'openviking_log_recall_like'])
    if group == 'row4-compat-primary':
        required_gate_names.append('row4_coexistence_proved')

    passed = all(gate_checks[name]['passed'] for name in required_gate_names)
    return gate_checks, required_gate_names, passed


def run_probe(group: str, run_id: str) -> None:
    spec = get_group_spec(group)
    required_paths = _runtime_gate(group)
    env = merged_env()
    base_url = env['OPENCLAW_BASE_URL']
    token = env['OPENCLAW_GATEWAY_TOKEN']
    user = f'repro-{run_id}-{group}-probe'
    mode = 'smoke'
    stage = 'probe'
    root_path = run_root(mode, run_id, group, stage)
    ensure_fresh_dir(root_path, 'probe run root')
    config_start = _current_config_state(group, required_paths)
    log_baseline = _log_baseline(env.get('OPENVIKING_LOG_FILE'))
    snapshot = capture_group_snapshot(group, run_id, root_path)
    runtime_arch = snapshot.get('runtime_architecture') or {}

    ingest_records = []
    for key, value in PROBE_FACTS:
        reply, usage = gateway_send(base_url, token, user, f'[probe-ingest] remember this fact: {key} = {value}')
        ingest_records.append({'fact_key': key, 'fact_value': value, 'reply': reply, 'usage': usage})

    qa_records = []
    correct = 0
    for question, expected in PROBE_QUESTIONS:
        reply, usage = gateway_send(base_url, token, user, question)
        is_correct = expected.lower() in reply.lower()
        if is_correct:
            correct += 1
        qa_records.append({'question': question, 'expected': expected, 'response': reply, 'usage': usage, 'is_correct': is_correct})

    usage_counts = _qa_usage_counts(qa_records)
    health_result = _health_status(env.get('OPENVIKING_HEALTH_URL')) if spec.get('require_openviking_health') else {'required': False, 'passed': True}
    log_trace = _read_log_delta(log_baseline)
    if log_trace is not None:
        (root_path / 'openviking.log.delta.txt').write_text((log_trace.get('delta_excerpt') or ''), encoding='utf-8')

    gate_checks, required_gate_names, passed = _build_probe_gate_checks(
        group=group,
        spec=spec,
        correct=correct,
        usage_counts=usage_counts,
        runtime_arch=runtime_arch,
        health_result=health_result,
        log_trace=log_trace,
    )

    result = {
        'group': group,
        'run_id': run_id,
        'stage': 'probe',
        'captured_at': utc_now(),
        'probe_user': user,
        'ingest_records': ingest_records,
        'qa_records': qa_records,
        'correct': correct,
        'total': len(PROBE_QUESTIONS),
        'passed': passed,
        'required_gate_names': required_gate_names,
        'gate_checks': gate_checks,
        'qa_usage_missing_count': usage_counts['qa_usage_missing_count'],
        'qa_usage_zero_count': usage_counts['qa_usage_zero_count'],
        'qa_usage_nonzero_count': usage_counts['qa_usage_nonzero_count'],
        'openviking_health': health_result,
        'openviking_log_trace': log_trace,
    }
    write_json(root_path / 'probe_result.json', result)
    _write_config_drift(root_path, group, required_paths, config_start)
    print(json.dumps({'probe_root': relpath(root_path), 'passed': result['passed'], 'score': f"{correct}/{len(PROBE_QUESTIONS)}"}, ensure_ascii=False, indent=2))
    if not passed:
        raise SystemExit(2)


def run_eval_stage(group: str, run_id: str, stage: str) -> None:
    if stage not in STAGE_PRESETS:
        raise SystemExit(f'unsupported stage: {stage}')

    spec = get_group_spec(group)
    claim = get_claim_decision(group)
    required_paths = _runtime_gate(group)
    env = merged_env()
    base_url = env['OPENCLAW_BASE_URL']
    token = env['OPENCLAW_GATEWAY_TOKEN']
    eval_python = env.get('EVAL_PYTHON', 'python3')

    preset = STAGE_PRESETS[stage]
    mode = preset['mode']
    root_path = run_root(mode, run_id, group, stage if mode == 'smoke' else None)
    ensure_fresh_dir(root_path, 'run root')

    storage = storage_root(run_id, group)
    ensure_fresh_dir(storage, 'storage root')
    ensure_dir(storage / 'cache')
    if spec['expected_storage'].get('lancedb'):
        ensure_dir(storage / 'lancedb')
    if spec['expected_storage'].get('openviking_workspace'):
        ensure_dir(storage / 'openviking-workspace')

    config_start = _current_config_state(group, required_paths)
    snapshot = capture_group_snapshot(group, run_id, root_path)
    runtime_arch = snapshot.get('runtime_architecture') or {}
    if runtime_arch.get('overall_passed') is not True:
        _write_config_drift(root_path, group, required_paths, config_start)
        raise SystemExit('runtime architecture proof failed before run: ' + '; '.join(runtime_arch.get('blocking_reasons', [])))

    run_spec = {
        'group': group,
        'run_id': run_id,
        'stage': stage,
        'mode': mode,
        'claim_class': claim['effective_claim_class'],
        'target_claim_class': claim['target_claim_class'],
        'group_spec': spec,
        'tail_literal': TAIL_LITERAL,
        'parallel': PARALLEL,
        'samples': preset['samples'],
        'qa_count': preset['qa_count'],
        'benchmark_path': relpath(BENCHMARK_PATH),
        'openclaw_base_url': base_url,
        'gateway_only': True,
        'forbid_eval_viking_flag': True,
        'config_snapshot_path': relpath(root_path / 'config_snapshot.json'),
        'required_actual_configs': {key: str(path) for key, path in required_paths.items()},
        'runtime_architecture_precheck': runtime_arch,
        'created_at': utc_now(),
    }
    write_json(root_path / 'run_spec.json', run_spec)

    run_meta: dict[str, Any] = {'samples': [], 'started_at': utc_now(), 'commands': []}
    for sample_idx in preset['samples']:
        sroot = sample_root(mode, run_id, group, sample_idx, stage if mode == 'smoke' else None)
        ensure_fresh_dir(sroot, f'sample root {sample_idx}')
        uid = user_id(run_id, group, sample_idx)
        ingest_cmd = [
            eval_python,
            str(OPENCLAW_EVAL_DIR / 'eval.py'),
            'ingest',
            str(BENCHMARK_PATH),
            '--base-url',
            base_url,
            '--token',
            token,
            '--sample',
            str(sample_idx),
            '--user',
            uid,
            '--tail',
            TAIL_LITERAL,
            '--output',
            str(sroot / 'ingest.txt'),
        ]
        qa_cmd = [
            eval_python,
            str(OPENCLAW_EVAL_DIR / 'eval.py'),
            'qa',
            str(BENCHMARK_PATH),
            '--base-url',
            base_url,
            '--token',
            token,
            '--sample',
            str(sample_idx),
            '--user',
            uid,
            '-p',
            str(PARALLEL),
            '--output',
            str(sroot / 'qa.txt'),
        ]
        if preset['qa_count'] is not None:
            qa_cmd.extend(['--count', str(preset['qa_count'])])

        ingest_cp = subprocess.run(ingest_cmd, text=True, capture_output=True, env=env)
        (sroot / 'ingest.console.log').write_text((ingest_cp.stdout or '') + '\n' + (ingest_cp.stderr or ''), encoding='utf-8')
        if ingest_cp.returncode != 0:
            raise SystemExit(f'ingest failed for {group} sample {sample_idx}; see {relpath(sroot / "ingest.console.log")}')

        qa_cp = subprocess.run(qa_cmd, text=True, capture_output=True, env=env)
        (sroot / 'qa.console.log').write_text((qa_cp.stdout or '') + '\n' + (qa_cp.stderr or ''), encoding='utf-8')
        if qa_cp.returncode != 0:
            raise SystemExit(f'qa failed for {group} sample {sample_idx}; see {relpath(sroot / "qa.console.log")}')

        candidates = sorted(sroot.glob('qa.txt.*.jsonl'))
        if len(candidates) != 1:
            raise SystemExit(f'expected exactly one qa.txt.*.jsonl under {path_label(sroot)}, got {len(candidates)}')
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
        run_meta['commands'].append({'sample_idx': sample_idx, 'ingest_command': ingest_cmd, 'qa_command': qa_cmd})

    run_meta['finished_at'] = utc_now()
    write_json(root_path / 'run_meta.json', run_meta)
    _write_config_drift(root_path, group, required_paths, config_start)
    print(json.dumps({'run_root': relpath(root_path), 'stage': stage, 'mode': mode, 'samples': preset['samples']}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('--stage', choices=['probe', 'micro', 'extended', 'full'], required=True)
    args = parser.parse_args()
    if args.stage == 'probe':
        run_probe(args.group, args.run_id)
    else:
        run_eval_stage(args.group, args.run_id, args.stage)


if __name__ == '__main__':
    main()
