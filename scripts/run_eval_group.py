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
    is_relative_to,
    load_json,
    merged_env,
    path_label,
    relpath,
    render_placeholders,
    run_root,
    runtime_env_file_path,
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
    counts = manifest.get('counts') or {}
    if counts.get('filtered_total_qas') != 1540:
        raise SystemExit('benchmark/manifest.json does not certify 1540 filtered QA cases')
    if counts.get('raw_total_qas') != 1986:
        raise SystemExit('benchmark/manifest.json does not certify 1986 raw QA cases')

    source = manifest.get('source') or {}
    files = manifest.get('files') or {}
    source_path = ROOT / str(source.get('path') or '')
    raw_copy_path = ROOT / str(((files.get('locomo10_raw.json') or {}).get('path') or ''))
    filtered_path = ROOT / str(((files.get('locomo10_filtered_no_cat5.json') or {}).get('path') or ''))

    if not source_path.exists():
        raise SystemExit(f'benchmark source file missing: {path_label(source_path)}')
    if not raw_copy_path.exists():
        raise SystemExit(f'benchmark raw copy missing: {path_label(raw_copy_path)}')
    if not filtered_path.exists():
        raise SystemExit(f'benchmark filtered file missing: {path_label(filtered_path)}')

    source_sha = sha256_file(source_path)
    if source.get('sha256') and source_sha != source.get('sha256'):
        raise SystemExit('benchmark source sha256 drifted from manifest')
    raw_sha = sha256_file(raw_copy_path)
    if raw_sha != source_sha:
        raise SystemExit('benchmark raw copy is not byte-identical to vendored source')
    filtered_item = files.get('locomo10_filtered_no_cat5.json') or {}
    if filtered_item.get('sha256') and sha256_file(filtered_path) != filtered_item.get('sha256'):
        raise SystemExit('benchmark filtered file sha256 drifted from manifest')
    if BENCHMARK_PATH.resolve() != filtered_path.resolve():
        raise SystemExit('BENCHMARK_PATH drifted from benchmark manifest primary filtered path')



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



def _resolve_env_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path



def _assert_materialization_binding(group: str, run_id: str, env: dict[str, str]) -> dict[str, Any]:
    runtime_env_raw = env.get('REPRO_RUNTIME_ENV_FILE')
    if not runtime_env_raw:
        runtime_env_path = runtime_env_file_path()
        runtime_env_raw = str(runtime_env_path) if runtime_env_path else None
    if not runtime_env_raw:
        raise SystemExit("formal wrapper requires REPRO_RUNTIME_ENV_FILE; run 'make materialize GROUP=<group> RUN_ID=<run_id>' first")
    runtime_env_path = _resolve_env_path(runtime_env_raw)
    if runtime_env_path is None or not runtime_env_path.exists():
        raise SystemExit(f'REPRO_RUNTIME_ENV_FILE not found: {runtime_env_raw}')

    manifest_raw = env.get('REPRO_MATERIALIZATION_MANIFEST')
    if not manifest_raw:
        raise SystemExit('missing REPRO_MATERIALIZATION_MANIFEST in runtime env; rerun materialize')
    manifest_path = _resolve_env_path(manifest_raw)
    if manifest_path is None or not manifest_path.exists():
        raise SystemExit(f'REPRO_MATERIALIZATION_MANIFEST not found: {manifest_raw}')

    runtime_dir_raw = env.get('REPRO_MATERIALIZATION_DIR')
    if not runtime_dir_raw:
        raise SystemExit('missing REPRO_MATERIALIZATION_DIR in runtime env; rerun materialize')
    runtime_dir = _resolve_env_path(runtime_dir_raw)
    if runtime_dir is None or not runtime_dir.exists():
        raise SystemExit(f'REPRO_MATERIALIZATION_DIR not found: {runtime_dir_raw}')

    if runtime_dir.name != group or runtime_dir.parent.name != run_id:
        raise SystemExit(f'materialization runtime dir does not match requested run_id/group: {runtime_dir}')

    manifest = load_json(manifest_path)
    if manifest.get('group') != group:
        raise SystemExit(f'materialization manifest group mismatch: expected {group}, got {manifest.get("group")}')
    if manifest.get('run_id') != run_id:
        raise SystemExit(f'materialization manifest run_id mismatch: expected {run_id}, got {manifest.get("run_id")}')

    exported = manifest.get('materialized_exports') or {}
    runtime_isolation = manifest.get('runtime_isolation') or {}
    storage_dir = storage_root(run_id, group).resolve()

    runtime_env_file = _resolve_env_path(exported.get('REPRO_RUNTIME_ENV_FILE') or env.get('REPRO_RUNTIME_ENV_FILE'))
    if runtime_env_file != runtime_env_path:
        raise SystemExit('runtime env file path drifted from materialization manifest')

    manifest_export_path = _resolve_env_path(exported.get('REPRO_MATERIALIZATION_MANIFEST') or env.get('REPRO_MATERIALIZATION_MANIFEST'))
    if manifest_export_path != manifest_path:
        raise SystemExit('materialization manifest path drifted from exported runtime env')

    runtime_dir_export = _resolve_env_path(exported.get('REPRO_MATERIALIZATION_DIR') or env.get('REPRO_MATERIALIZATION_DIR'))
    if runtime_dir_export != runtime_dir:
        raise SystemExit('materialization runtime dir drifted from exported runtime env')

    openclaw_config = _resolve_env_path(env.get('OPENCLAW_CONFIG_PATH'))
    if openclaw_config is None or not openclaw_config.exists():
        raise SystemExit('OPENCLAW_CONFIG_PATH missing or unreadable in runtime env')
    expected_openclaw = _resolve_env_path(exported.get('OPENCLAW_CONFIG_PATH'))
    if expected_openclaw != openclaw_config:
        raise SystemExit('OPENCLAW_CONFIG_PATH drifted from materialization manifest')
    if openclaw_config.parent.resolve() != runtime_dir.resolve():
        raise SystemExit('OPENCLAW_CONFIG_PATH is not located under the bound runtime materialization dir')

    isolation_bindings: dict[str, str] = {}
    for env_key, runtime_key in [('OPENCLAW_HOME', 'openclaw_home'), ('OPENCLAW_STATE_DIR', 'openclaw_state_dir')]:
        resolved = _resolve_env_path(env.get(env_key) or exported.get(env_key) or runtime_isolation.get(runtime_key))
        if resolved is None or not resolved.exists():
            raise SystemExit(f'{env_key} missing or unreadable in runtime env')
        exported_path = _resolve_env_path(exported.get(env_key))
        if exported_path != resolved:
            raise SystemExit(f'{env_key} drifted from materialization manifest')
        runtime_isolation_path = _resolve_env_path(runtime_isolation.get(runtime_key))
        if runtime_isolation_path is not None and runtime_isolation_path != resolved:
            raise SystemExit(f'{env_key} drifted from materialization runtime_isolation')
        if not is_relative_to(resolved, storage_dir):
            raise SystemExit(f'{env_key} escaped bound storage root: {resolved}')
        isolation_bindings[env_key] = str(resolved)

    spec = get_group_spec(group)
    openviking_config: str | None = None
    workspace_path: str | None = None
    if spec.get('openviking_mode') == 'local':
        ov_path = _resolve_env_path(env.get('OPENVIKING_CONFIG_PATH'))
        if ov_path is None or not ov_path.exists():
            raise SystemExit('OPENVIKING_CONFIG_PATH missing or unreadable in runtime env')
        expected_ov = _resolve_env_path(exported.get('OPENVIKING_CONFIG_PATH'))
        if expected_ov != ov_path:
            raise SystemExit('OPENVIKING_CONFIG_PATH drifted from materialization manifest')
        if ov_path.parent.resolve() != runtime_dir.resolve():
            raise SystemExit('OPENVIKING_CONFIG_PATH is not located under the bound runtime materialization dir')
        openviking_config = str(ov_path)

        workspace_resolved = _resolve_env_path(
            env.get('OPENVIKING_WORKSPACE_PATH')
            or exported.get('OPENVIKING_WORKSPACE_PATH')
            or manifest.get('openviking_workspace_path')
        )
        if workspace_resolved is not None:
            if not workspace_resolved.exists():
                raise SystemExit(f'OPENVIKING_WORKSPACE_PATH not found: {workspace_resolved}')
            if not is_relative_to(workspace_resolved, storage_dir):
                raise SystemExit(f'OPENVIKING_WORKSPACE_PATH escaped bound storage root: {workspace_resolved}')
            workspace_path = str(workspace_resolved)

    return {
        'runtime_env_file': str(runtime_env_path),
        'materialization_manifest': str(manifest_path),
        'materialization_dir': str(runtime_dir),
        'materialization_mode': manifest.get('materialization_mode'),
        'replaced_previous_dir': manifest.get('replaced_previous_dir'),
        'openclaw_config_path': str(openclaw_config),
        'openclaw_home': isolation_bindings['OPENCLAW_HOME'],
        'openclaw_state_dir': isolation_bindings['OPENCLAW_STATE_DIR'],
        'openviking_config_path': openviking_config,
        'openviking_workspace_path': workspace_path,
        'runtime_isolation': runtime_isolation,
    }


def _bound_runtime_env(base_env: dict[str, str], binding: dict[str, Any]) -> dict[str, str]:
    env = dict(base_env)
    for key in ['runtime_env_file', 'materialization_manifest', 'materialization_dir']:
        value = binding.get(key)
        if value:
            env_key = {
                'runtime_env_file': 'REPRO_RUNTIME_ENV_FILE',
                'materialization_manifest': 'REPRO_MATERIALIZATION_MANIFEST',
                'materialization_dir': 'REPRO_MATERIALIZATION_DIR',
            }[key]
            env[env_key] = str(value)

    direct_mappings = {
        'openclaw_config_path': 'OPENCLAW_CONFIG_PATH',
        'openclaw_home': 'OPENCLAW_HOME',
        'openclaw_state_dir': 'OPENCLAW_STATE_DIR',
        'openviking_config_path': 'OPENVIKING_CONFIG_PATH',
        'openviking_workspace_path': 'OPENVIKING_WORKSPACE_PATH',
    }
    for binding_key, env_key in direct_mappings.items():
        value = binding.get(binding_key)
        if value:
            env[env_key] = str(value)
    return env


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
        return {
            'path': str(path),
            'exists_after_probe': False,
            'delta_bytes': 0,
            'capture_event_count': 0,
            'recall_event_count': 0,
            'find_event_count': 0,
            'parsed_events': [],
            'weak_text_hints': {'capture_like': False, 'recall_like': False, 'find_like': False},
        }

    stat = path.stat()
    start_size = int(baseline.get('size') or 0)
    same_inode = baseline.get('inode') == stat.st_ino and baseline.get('exists') is True
    read_from = start_size if same_inode and stat.st_size >= start_size else 0
    with path.open('rb') as f:
        f.seek(read_from)
        delta_bytes = f.read()
    text = delta_bytes.decode('utf-8', errors='ignore')
    lowered = text.lower()

    parsed_events: list[dict[str, Any]] = []
    capture_event_count = 0
    recall_event_count = 0
    find_event_count = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith('{'):
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        event_name = None
        for key in ('event', 'action', 'op', 'phase'):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                event_name = value.strip().lower()
                break
        if not event_name:
            continue
        parsed_events.append({'event': event_name})
        if 'capture' in event_name or 'commit' in event_name:
            capture_event_count += 1
        if 'recall' in event_name:
            recall_event_count += 1
        if 'find' in event_name or 'search' in event_name:
            find_event_count += 1

    return {
        'path': str(path),
        'exists_after_probe': True,
        'delta_bytes': len(delta_bytes),
        'parsed_events': parsed_events[:50],
        'capture_event_count': capture_event_count,
        'recall_event_count': recall_event_count,
        'find_event_count': find_event_count,
        'weak_text_hints': {
            'capture_like': 'capture' in lowered,
            'recall_like': 'recall' in lowered,
            'find_like': 'find' in lowered,
        },
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



def _workspace_snapshot(path: str | None) -> dict[str, Any] | None:
    workspace = _resolve_env_path(path)
    if workspace is None:
        return None
    snapshot: dict[str, Any] = {
        'path': str(workspace),
        'exists': workspace.exists(),
        'file_count': 0,
        'total_bytes': 0,
        'latest_mtime_ns': None,
        'files': {},
    }
    if not workspace.exists():
        return snapshot

    latest_mtime_ns = 0
    files: dict[str, dict[str, int]] = {}
    if workspace.is_file():
        stat = workspace.stat()
        files[workspace.name] = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
        latest_mtime_ns = stat.st_mtime_ns
    else:
        for child in sorted(workspace.rglob('*')):
            if not child.is_file():
                continue
            rel = child.relative_to(workspace).as_posix()
            stat = child.stat()
            files[rel] = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
            latest_mtime_ns = max(latest_mtime_ns, stat.st_mtime_ns)
    snapshot['files'] = files
    snapshot['file_count'] = len(files)
    snapshot['total_bytes'] = sum(item['size'] for item in files.values())
    snapshot['latest_mtime_ns'] = latest_mtime_ns or None
    return snapshot



def _workspace_delta(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any] | None:
    if before is None and after is None:
        return None
    before = before or {'path': None, 'exists': False, 'file_count': 0, 'total_bytes': 0, 'latest_mtime_ns': None, 'files': {}}
    after = after or {'path': None, 'exists': False, 'file_count': 0, 'total_bytes': 0, 'latest_mtime_ns': None, 'files': {}}
    before_files = before.get('files') or {}
    after_files = after.get('files') or {}
    new_files = sorted(set(after_files) - set(before_files))
    deleted_files = sorted(set(before_files) - set(after_files))
    changed_files = sorted(
        key for key in (set(before_files) & set(after_files)) if before_files[key] != after_files[key]
    )
    activity_detected = bool(
        new_files
        or deleted_files
        or changed_files
        or before.get('file_count') != after.get('file_count')
        or before.get('total_bytes') != after.get('total_bytes')
        or before.get('latest_mtime_ns') != after.get('latest_mtime_ns')
    )
    return {
        'path': after.get('path') or before.get('path'),
        'exists_before': before.get('exists'),
        'exists_after': after.get('exists'),
        'file_count_before': before.get('file_count', 0),
        'file_count_after': after.get('file_count', 0),
        'total_bytes_before': before.get('total_bytes', 0),
        'total_bytes_after': after.get('total_bytes', 0),
        'latest_mtime_ns_before': before.get('latest_mtime_ns'),
        'latest_mtime_ns_after': after.get('latest_mtime_ns'),
        'new_files': new_files,
        'deleted_files': deleted_files,
        'changed_files': changed_files,
        'activity_detected': activity_detected,
    }



def _find_first_numeric(value: Any, candidate_keys: set[str]) -> int | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in candidate_keys and not isinstance(item, bool):
                if isinstance(item, (int, float)):
                    return int(item)
                if isinstance(item, str) and item.strip().isdigit():
                    return int(item.strip())
        for item in value.values():
            found = _find_first_numeric(item, candidate_keys)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_first_numeric(item, candidate_keys)
            if found is not None:
                return found
    return None



def _read_openviking_diagnostics(env: dict[str, str]) -> dict[str, Any] | None:
    endpoint = (env.get('OPENVIKING_DIAGNOSTIC_ENDPOINT') or '').strip()
    command = (env.get('OPENVIKING_DIAGNOSTIC_CMD') or '').strip()
    if not endpoint and not command:
        return None

    payload: Any | None = None
    result: dict[str, Any]
    if endpoint:
        try:
            resp = requests.get(endpoint, timeout=10)
            resp.raise_for_status()
            payload = resp.json()
            result = {'source': 'endpoint', 'endpoint': endpoint, 'status_code': resp.status_code, 'payload': payload}
        except Exception as exc:
            return {'source': 'endpoint', 'endpoint': endpoint, 'passed': False, 'error': str(exc)}
    else:
        cp = subprocess.run(command, shell=True, text=True, capture_output=True, env=env)
        if cp.returncode != 0:
            return {'source': 'command', 'command': command, 'passed': False, 'returncode': cp.returncode, 'stderr': (cp.stderr or '')[:1000]}
        try:
            payload = json.loads(cp.stdout)
        except Exception as exc:
            return {'source': 'command', 'command': command, 'passed': False, 'error': f'invalid JSON diagnostics output: {exc}', 'stdout_excerpt': (cp.stdout or '')[:1000]}
        result = {'source': 'command', 'command': command, 'payload': payload}

    capture_count = _find_first_numeric(payload, {'capture_count', 'captureCount'}) or 0
    recall_count = _find_first_numeric(payload, {'recall_count', 'recallCount'}) or 0
    find_count = _find_first_numeric(payload, {'find_count', 'findCount'}) or 0
    result.update(
        {
            'passed': True,
            'capture_count': capture_count,
            'recall_count': recall_count,
            'find_count': find_count,
        }
    )
    return result



def _capture_evidence_gate(
    spec: dict[str, Any],
    diagnostics: dict[str, Any] | None,
    workspace_delta: dict[str, Any] | None,
    log_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    if not spec.get('require_openviking_health'):
        return {'passed': True, 'required': False, 'source': 'not_applicable', 'evidence_level': 'n/a'}
    if diagnostics and int(diagnostics.get('capture_count') or 0) > 0:
        return {'passed': True, 'required': True, 'source': 'diagnostics', 'evidence_level': 'strong', 'capture_count': int(diagnostics.get('capture_count') or 0)}
    if workspace_delta and workspace_delta.get('activity_detected'):
        return {'passed': True, 'required': True, 'source': 'workspace_delta', 'evidence_level': 'strong', 'activity_detected': True}
    if log_trace and int(log_trace.get('capture_event_count') or 0) > 0:
        return {'passed': True, 'required': True, 'source': 'structured_log', 'evidence_level': 'medium', 'capture_event_count': int(log_trace.get('capture_event_count') or 0)}
    return {
        'passed': False,
        'required': True,
        'source': 'none',
        'evidence_level': 'missing',
        'weak_text_hints': (log_trace or {}).get('weak_text_hints'),
    }



def _recall_evidence_gate(
    *,
    group: str,
    spec: dict[str, Any],
    correct: int,
    usage_counts: dict[str, int],
    runtime_arch: dict[str, Any],
    diagnostics: dict[str, Any] | None,
    log_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    if not spec.get('require_openviking_health'):
        return {'passed': True, 'required': False, 'source': 'not_applicable', 'evidence_level': 'n/a'}
    if diagnostics and (int(diagnostics.get('recall_count') or 0) > 0 or int(diagnostics.get('find_count') or 0) > 0):
        return {
            'passed': True,
            'required': True,
            'source': 'diagnostics',
            'evidence_level': 'strong',
            'recall_count': int(diagnostics.get('recall_count') or 0),
            'find_count': int(diagnostics.get('find_count') or 0),
        }
    if log_trace and (int(log_trace.get('recall_event_count') or 0) > 0 or int(log_trace.get('find_event_count') or 0) > 0):
        return {
            'passed': True,
            'required': True,
            'source': 'structured_log',
            'evidence_level': 'medium',
            'recall_event_count': int(log_trace.get('recall_event_count') or 0),
            'find_event_count': int(log_trace.get('find_event_count') or 0),
        }

    if (
        group == 'row3-openviking-minus-core'
        and runtime_arch.get('overall_passed') is True
        and correct >= 2
        and usage_counts['qa_usage_nonzero_count'] == len(PROBE_QUESTIONS)
    ):
        return {
            'passed': True,
            'required': True,
            'source': 'behavior_runtime_combo',
            'evidence_level': 'medium',
            'observed_correct': correct,
            'nonzero_count': usage_counts['qa_usage_nonzero_count'],
        }

    return {
        'passed': False,
        'required': True,
        'source': 'none',
        'evidence_level': 'missing',
        'weak_text_hints': (log_trace or {}).get('weak_text_hints'),
    }



def _build_probe_gate_checks(
    *,
    group: str,
    spec: dict[str, Any],
    correct: int,
    usage_counts: dict[str, int],
    runtime_arch: dict[str, Any],
    health_result: dict[str, Any] | None,
    log_trace: dict[str, Any] | None,
    workspace_delta: dict[str, Any] | None,
    diagnostics: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, Any]], list[str], bool]:
    capture_gate = _capture_evidence_gate(spec, diagnostics, workspace_delta, log_trace)
    recall_gate = _recall_evidence_gate(
        group=group,
        spec=spec,
        correct=correct,
        usage_counts=usage_counts,
        runtime_arch=runtime_arch,
        diagnostics=diagnostics,
        log_trace=log_trace,
    )
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
        'openviking_capture_evidence': capture_gate,
        'openviking_recall_evidence': recall_gate,
    }
    if group == 'row4-compat-primary':
        gate_checks['row4_coexistence_proved'] = {
            'passed': runtime_arch.get('checks', {}).get('row4_coexistence_proved') is True,
            'required': True,
        }

    required_gate_names = ['memory_recall_accuracy', 'qa_usage_nonzero', 'runtime_architecture']
    if spec.get('require_openviking_health'):
        required_gate_names.extend(['openviking_health', 'openviking_capture_evidence', 'openviking_recall_evidence'])
    if group == 'row4-compat-primary':
        required_gate_names.append('row4_coexistence_proved')

    passed = all(gate_checks[name]['passed'] for name in required_gate_names)
    return gate_checks, required_gate_names, passed



def run_probe(group: str, run_id: str) -> None:
    spec = get_group_spec(group)
    required_paths = _runtime_gate(group)
    shell_env = merged_env()
    binding = _assert_materialization_binding(group, run_id, shell_env)
    env = _bound_runtime_env(shell_env, binding)
    base_url = env['OPENCLAW_BASE_URL']
    token = env['OPENCLAW_GATEWAY_TOKEN']
    user = f'repro-{run_id}-{group}-probe'
    mode = 'smoke'
    stage = 'probe'
    root_path = run_root(mode, run_id, group, stage)
    ensure_fresh_dir(root_path, 'probe run root')
    config_start = _current_config_state(group, required_paths)
    log_baseline = _log_baseline(env.get('OPENVIKING_LOG_FILE'))
    workspace_before = _workspace_snapshot(env.get('OPENVIKING_WORKSPACE_PATH'))

    try:
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
        workspace_after = _workspace_snapshot(env.get('OPENVIKING_WORKSPACE_PATH'))
        workspace_delta = _workspace_delta(workspace_before, workspace_after)
        diagnostics = _read_openviking_diagnostics(env)

        if log_trace is not None:
            (root_path / 'openviking.log.delta.txt').write_text((log_trace.get('delta_excerpt') or ''), encoding='utf-8')
            write_json(root_path / 'openviking.log.trace.json', log_trace)
        if workspace_before is not None:
            write_json(root_path / 'openviking.workspace.before.json', workspace_before)
        if workspace_after is not None:
            write_json(root_path / 'openviking.workspace.after.json', workspace_after)
        if workspace_delta is not None:
            write_json(root_path / 'openviking.workspace.delta.json', workspace_delta)
        if diagnostics is not None:
            write_json(root_path / 'openviking.diagnostics.json', diagnostics)
        write_json(root_path / 'materialization_binding.json', binding)

        gate_checks, required_gate_names, passed = _build_probe_gate_checks(
            group=group,
            spec=spec,
            correct=correct,
            usage_counts=usage_counts,
            runtime_arch=runtime_arch,
            health_result=health_result,
            log_trace=log_trace,
            workspace_delta=workspace_delta,
            diagnostics=diagnostics,
        )

        result = {
            'group': group,
            'run_id': run_id,
            'stage': 'probe',
            'captured_at': utc_now(),
            'probe_user': user,
            'materialization_binding': binding,
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
            'openviking_workspace_before': workspace_before,
            'openviking_workspace_after': workspace_after,
            'openviking_workspace_delta': workspace_delta,
            'openviking_diagnostics': diagnostics,
        }
        write_json(root_path / 'probe_result.json', result)
        print(json.dumps({'probe_root': relpath(root_path), 'passed': result['passed'], 'score': f"{correct}/{len(PROBE_QUESTIONS)}"}, ensure_ascii=False, indent=2))
        if not passed:
            raise SystemExit(2)
    finally:
        _write_config_drift(root_path, group, required_paths, config_start)


def run_eval_stage(group: str, run_id: str, stage: str) -> None:
    if stage not in STAGE_PRESETS:
        raise SystemExit(f'unsupported stage: {stage}')

    spec = get_group_spec(group)
    claim = get_claim_decision(group)
    required_paths = _runtime_gate(group)
    shell_env = merged_env()
    binding = _assert_materialization_binding(group, run_id, shell_env)
    env = _bound_runtime_env(shell_env, binding)
    base_url = env['OPENCLAW_BASE_URL']
    token = env['OPENCLAW_GATEWAY_TOKEN']
    eval_python = env.get('EVAL_PYTHON', 'python3')

    preset = STAGE_PRESETS[stage]
    mode = preset['mode']
    root_path = run_root(mode, run_id, group, stage if mode == 'smoke' else None)
    ensure_fresh_dir(root_path, 'run root')

    storage = storage_root(run_id, group)
    ensure_dir(storage)
    ensure_dir(Path(binding['openclaw_home']))
    ensure_dir(Path(binding['openclaw_state_dir']))
    ensure_dir(storage / 'cache')
    if spec['expected_storage'].get('lancedb'):
        ensure_dir(storage / 'lancedb')
    if spec['expected_storage'].get('openviking_workspace') and binding.get('openviking_workspace_path'):
        ensure_dir(Path(binding['openviking_workspace_path']))

    config_start = _current_config_state(group, required_paths)
    try:
        snapshot = capture_group_snapshot(group, run_id, root_path)
        runtime_arch = snapshot.get('runtime_architecture') or {}
        if runtime_arch.get('overall_passed') is not True:
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
            'benchmark_manifest_path': relpath(BENCHMARK_MANIFEST_PATH),
            'openclaw_base_url': base_url,
            'gateway_only': True,
            'forbid_eval_viking_flag': True,
            'config_snapshot_path': relpath(root_path / 'config_snapshot.json'),
            'required_actual_configs': {key: str(path) for key, path in required_paths.items()},
            'runtime_architecture_precheck': runtime_arch,
            'materialization_manifest': binding['materialization_manifest'],
            'materialization_dir': binding['materialization_dir'],
            'runtime_env_file': binding['runtime_env_file'],
            'materialization_mode': binding.get('materialization_mode'),
            'runtime_isolation': {
                'openclaw_home': binding['openclaw_home'],
                'openclaw_state_dir': binding['openclaw_state_dir'],
                'openviking_workspace_path': binding.get('openviking_workspace_path'),
            },
            'openviking_workspace_path': binding.get('openviking_workspace_path'),
            'created_at': utc_now(),
        }
        write_json(root_path / 'run_spec.json', run_spec)
        write_json(root_path / 'materialization_binding.json', binding)

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

            ingest_cp = subprocess.run(ingest_cmd, text=True, capture_output=True, env=env, cwd=ROOT)
            (sroot / 'ingest.console.log').write_text((ingest_cp.stdout or '') + '\n' + (ingest_cp.stderr or ''), encoding='utf-8')
            if ingest_cp.returncode != 0:
                raise SystemExit(f'ingest failed for {group} sample {sample_idx}; see {relpath(sroot / "ingest.console.log")}')

            qa_cp = subprocess.run(qa_cmd, text=True, capture_output=True, env=env, cwd=ROOT)
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
        print(json.dumps({'run_root': relpath(root_path), 'stage': stage, 'mode': mode, 'samples': preset['samples']}, ensure_ascii=False, indent=2))
    finally:
        _write_config_drift(root_path, group, required_paths, config_start)


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
