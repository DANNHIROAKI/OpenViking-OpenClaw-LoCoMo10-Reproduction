from __future__ import annotations

import json
from pathlib import Path

import pytest

import run_eval_group as reg
from _common import ROOT


def _prepare_probe_monkeypatch(monkeypatch, tmp_path: Path, *, usage_tokens: list[int], row4_ok: bool = True) -> Path:
    run_dir = ROOT / 'tests_tmp' / tmp_path.name / 'probe-run'

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
    monkeypatch.setattr(reg, '_read_log_delta', lambda baseline: {'capture_like': True, 'recall_like': True, 'delta_excerpt': 'capture recall'})
    monkeypatch.setattr(reg, '_health_status', lambda url: {'passed': True, 'status_code': 200, 'url': url})

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


def test_probe_passes_when_all_barriers_pass(monkeypatch, tmp_path: Path) -> None:
    run_dir = _prepare_probe_monkeypatch(monkeypatch, tmp_path, usage_tokens=[1, 1, 1], row4_ok=True)
    reg.run_probe('row4-compat-primary', 'probe-pass')
    result = json.loads((run_dir / 'probe_result.json').read_text(encoding='utf-8'))
    assert result['passed'] is True
    assert result['gate_checks']['qa_usage_nonzero']['passed'] is True
    assert result['gate_checks']['row4_coexistence_proved']['passed'] is True


def test_probe_fails_when_usage_is_zero(monkeypatch, tmp_path: Path) -> None:
    run_dir = _prepare_probe_monkeypatch(monkeypatch, tmp_path, usage_tokens=[0, 0, 0], row4_ok=True)
    with pytest.raises(SystemExit) as exc:
        reg.run_probe('row4-compat-primary', 'probe-fail')
    assert exc.value.code == 2
    result = json.loads((run_dir / 'probe_result.json').read_text(encoding='utf-8'))
    assert result['passed'] is False
    assert result['gate_checks']['qa_usage_nonzero']['passed'] is False
