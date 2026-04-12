from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import run_eval_group as reg
from _common import ROOT



def _prepare_probe_monkeypatch(
    monkeypatch,
    tmp_path: Path,
    *,
    group: str,
    usage_tokens: list[int],
    row4_ok: bool = True,
    log_trace: dict | None = None,
    workspace_before: dict | None = None,
    workspace_after: dict | None = None,
    workspace_delta: dict | None = None,
    diagnostics: dict | None = None,
) -> Path:
    run_dir = ROOT / 'tests_tmp' / tmp_path.name / 'probe-run'
    if run_dir.exists():
        shutil.rmtree(run_dir)

    def fake_run_root(mode: str, run_id: str, group: str, stage: str | None = None) -> Path:
        return run_dir

    def fake_ensure_fresh_dir(path: Path, label: str | None = None) -> Path:
        path.mkdir(parents=True, exist_ok=False)
        return path

    monkeypatch.setattr(reg, '_runtime_gate', lambda group: {})
    monkeypatch.setattr(reg, 'run_root', fake_run_root)
    monkeypatch.setattr(reg, 'ensure_fresh_dir', fake_ensure_fresh_dir)
    monkeypatch.setattr(reg, '_current_config_state', lambda group, req: {})
    monkeypatch.setattr(reg, '_write_config_drift', lambda *args, **kwargs: None)
    monkeypatch.setattr(
        reg,
        'merged_env',
        lambda: {
            'OPENCLAW_BASE_URL': 'http://gateway',
            'OPENCLAW_GATEWAY_TOKEN': 'token',
            'OPENVIKING_HEALTH_URL': 'http://health',
            'OPENVIKING_LOG_FILE': '/tmp/openviking-test.log',
            'OPENVIKING_WORKSPACE_PATH': '/tmp/openviking-workspace',
        },
    )
    monkeypatch.setattr(
        reg,
        '_assert_materialization_binding',
        lambda group, run_id, env: {
            'runtime_env_file': '/tmp/exports.env',
            'materialization_manifest': '/tmp/materialization_manifest.json',
            'materialization_dir': f'/tmp/{run_id}/{group}',
            'openviking_workspace_path': '/tmp/openviking-workspace',
        },
    )
    monkeypatch.setattr(
        reg,
        'capture_group_snapshot',
        lambda group, run_id, root_path: {
            'runtime_architecture': {
                'overall_passed': True,
                'blocking_reasons': [],
                'checks': {'row4_coexistence_proved': row4_ok},
            }
        },
    )
    monkeypatch.setattr(reg, '_log_baseline', lambda log: {'path': log, 'size': 0, 'exists': False, 'inode': None})
    monkeypatch.setattr(
        reg,
        '_read_log_delta',
        lambda baseline: log_trace
        or {
            'capture_event_count': 0,
            'recall_event_count': 0,
            'find_event_count': 0,
            'weak_text_hints': {'capture_like': False, 'recall_like': False, 'find_like': False},
            'delta_excerpt': '',
        },
    )
    monkeypatch.setattr(reg, '_health_status', lambda url: {'passed': True, 'status_code': 200, 'url': url})

    workspace_snapshots = iter(
        [
            workspace_before if workspace_before is not None else {'path': '/tmp/openviking-workspace', 'exists': False, 'files': {}, 'file_count': 0, 'total_bytes': 0, 'latest_mtime_ns': None},
            workspace_after if workspace_after is not None else {'path': '/tmp/openviking-workspace', 'exists': False, 'files': {}, 'file_count': 0, 'total_bytes': 0, 'latest_mtime_ns': None},
        ]
    )
    monkeypatch.setattr(reg, '_workspace_snapshot', lambda path: next(workspace_snapshots))
    monkeypatch.setattr(
        reg,
        '_workspace_delta',
        lambda before, after: workspace_delta
        if workspace_delta is not None
        else {
            'path': '/tmp/openviking-workspace',
            'activity_detected': False,
            'new_files': [],
            'changed_files': [],
            'deleted_files': [],
            'file_count_before': 0,
            'file_count_after': 0,
            'total_bytes_before': 0,
            'total_bytes_after': 0,
            'latest_mtime_ns_before': None,
            'latest_mtime_ns_after': None,
        },
    )
    monkeypatch.setattr(reg, '_read_openviking_diagnostics', lambda env: diagnostics)

    replies = [
        ('ok', {'input_tokens': 1}),
        ('ok', {'input_tokens': 1}),
        ('ok', {'input_tokens': 1}),
        ('fish', {'input_tokens': usage_tokens[0]}),
        ('blue', {'input_tokens': usage_tokens[1]}),
        ('glacier-pine', {'input_tokens': usage_tokens[2]}),
    ]
    iterator = iter(replies)
    monkeypatch.setattr(reg, 'gateway_send', lambda *args, **kwargs: next(iterator))
    return run_dir



def test_probe_passes_with_workspace_delta_without_log_keywords(monkeypatch, tmp_path: Path) -> None:
    run_dir = _prepare_probe_monkeypatch(
        monkeypatch,
        tmp_path,
        group='row4-compat-primary',
        usage_tokens=[1, 1, 1],
        row4_ok=True,
        workspace_delta={
            'path': '/tmp/openviking-workspace',
            'activity_detected': True,
            'new_files': ['capture.jsonl'],
            'changed_files': [],
            'deleted_files': [],
            'file_count_before': 0,
            'file_count_after': 1,
            'total_bytes_before': 0,
            'total_bytes_after': 12,
            'latest_mtime_ns_before': None,
            'latest_mtime_ns_after': 123,
        },
        log_trace={
            'capture_event_count': 0,
            'recall_event_count': 1,
            'find_event_count': 0,
            'weak_text_hints': {'capture_like': False, 'recall_like': False, 'find_like': False},
            'delta_excerpt': '',
        },
        diagnostics=None,
    )
    reg.run_probe('row4-compat-primary', 'probe-pass-workspace')
    result = json.loads((run_dir / 'probe_result.json').read_text(encoding='utf-8'))
    assert result['passed'] is True
    assert result['gate_checks']['openviking_capture_evidence']['source'] == 'workspace_delta'



def test_probe_passes_with_diagnostics_without_log_keywords(monkeypatch, tmp_path: Path) -> None:
    run_dir = _prepare_probe_monkeypatch(
        monkeypatch,
        tmp_path,
        group='row4-compat-primary',
        usage_tokens=[1, 1, 1],
        row4_ok=True,
        log_trace={
            'capture_event_count': 0,
            'recall_event_count': 0,
            'find_event_count': 0,
            'weak_text_hints': {'capture_like': False, 'recall_like': False, 'find_like': False},
            'delta_excerpt': '',
        },
        diagnostics={'source': 'endpoint', 'passed': True, 'capture_count': 1, 'recall_count': 1, 'find_count': 0},
    )
    reg.run_probe('row4-compat-primary', 'probe-pass-diag')
    result = json.loads((run_dir / 'probe_result.json').read_text(encoding='utf-8'))
    assert result['passed'] is True
    assert result['gate_checks']['openviking_capture_evidence']['source'] == 'diagnostics'
    assert result['gate_checks']['openviking_recall_evidence']['source'] == 'diagnostics'



def test_probe_fails_when_usage_is_zero(monkeypatch, tmp_path: Path) -> None:
    run_dir = _prepare_probe_monkeypatch(
        monkeypatch,
        tmp_path,
        group='row4-compat-primary',
        usage_tokens=[0, 0, 0],
        row4_ok=True,
        workspace_delta={
            'path': '/tmp/openviking-workspace',
            'activity_detected': True,
            'new_files': ['capture.jsonl'],
            'changed_files': [],
            'deleted_files': [],
            'file_count_before': 0,
            'file_count_after': 1,
            'total_bytes_before': 0,
            'total_bytes_after': 12,
            'latest_mtime_ns_before': None,
            'latest_mtime_ns_after': 123,
        },
        diagnostics={'source': 'endpoint', 'passed': True, 'capture_count': 1, 'recall_count': 1, 'find_count': 0},
    )
    with pytest.raises(SystemExit) as exc:
        reg.run_probe('row4-compat-primary', 'probe-fail-usage')
    assert exc.value.code == 2
    result = json.loads((run_dir / 'probe_result.json').read_text(encoding='utf-8'))
    assert result['passed'] is False
    assert result['gate_checks']['qa_usage_nonzero']['passed'] is False



def test_row4_requires_structured_recall_evidence_not_behavior_only(monkeypatch, tmp_path: Path) -> None:
    run_dir = _prepare_probe_monkeypatch(
        monkeypatch,
        tmp_path,
        group='row4-compat-primary',
        usage_tokens=[1, 1, 1],
        row4_ok=True,
        workspace_delta={
            'path': '/tmp/openviking-workspace',
            'activity_detected': True,
            'new_files': ['capture.jsonl'],
            'changed_files': [],
            'deleted_files': [],
            'file_count_before': 0,
            'file_count_after': 1,
            'total_bytes_before': 0,
            'total_bytes_after': 12,
            'latest_mtime_ns_before': None,
            'latest_mtime_ns_after': 123,
        },
        log_trace={
            'capture_event_count': 0,
            'recall_event_count': 0,
            'find_event_count': 0,
            'weak_text_hints': {'capture_like': False, 'recall_like': False, 'find_like': False},
            'delta_excerpt': '',
        },
        diagnostics=None,
    )
    with pytest.raises(SystemExit) as exc:
        reg.run_probe('row4-compat-primary', 'probe-row4-recall-fail')
    assert exc.value.code == 2
    result = json.loads((run_dir / 'probe_result.json').read_text(encoding='utf-8'))
    assert result['gate_checks']['openviking_recall_evidence']['passed'] is False



def test_row3_behavior_runtime_combo_can_satisfy_recall_without_log_keywords(monkeypatch, tmp_path: Path) -> None:
    run_dir = _prepare_probe_monkeypatch(
        monkeypatch,
        tmp_path,
        group='row3-openviking-minus-core',
        usage_tokens=[1, 1, 1],
        row4_ok=True,
        workspace_delta={
            'path': '/tmp/openviking-workspace',
            'activity_detected': True,
            'new_files': ['capture.jsonl'],
            'changed_files': [],
            'deleted_files': [],
            'file_count_before': 0,
            'file_count_after': 1,
            'total_bytes_before': 0,
            'total_bytes_after': 12,
            'latest_mtime_ns_before': None,
            'latest_mtime_ns_after': 123,
        },
        log_trace={
            'capture_event_count': 0,
            'recall_event_count': 0,
            'find_event_count': 0,
            'weak_text_hints': {'capture_like': False, 'recall_like': False, 'find_like': False},
            'delta_excerpt': '',
        },
        diagnostics=None,
    )
    reg.run_probe('row3-openviking-minus-core', 'probe-row3-behavior-pass')
    result = json.loads((run_dir / 'probe_result.json').read_text(encoding='utf-8'))
    assert result['passed'] is True
    assert result['gate_checks']['openviking_recall_evidence']['source'] == 'behavior_runtime_combo'
