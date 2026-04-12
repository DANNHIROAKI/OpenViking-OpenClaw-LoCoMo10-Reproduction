from __future__ import annotations

import json
from pathlib import Path

import capture_group_snapshot as cgs
import finalize_group
from _common import ROOT, write_json


def test_capture_snapshot_writes_normalized_and_runtime_assertion(monkeypatch, tmp_path: Path) -> None:
    oc_path = tmp_path / 'openclaw.json'
    ov_path = tmp_path / 'ov.conf'
    write_json(oc_path, {'plugins': {'slots': {'memory': 'memory-core', 'contextEngine': 'openviking'}}})
    write_json(ov_path, {'server': {'port': 8080}})
    monkeypatch.setenv('OPENCLAW_CONFIG_PATH', str(oc_path))
    monkeypatch.setenv('OPENVIKING_CONFIG_PATH', str(ov_path))

    def fake_run_shell(command: str, **kwargs):
        class CP:
            def __init__(self, stdout: str):
                self.stdout = stdout
                self.stderr = ''
                self.returncode = 0
        if 'plugins list' in command:
            return CP('{"slots":{"memory":"memory-core","contextEngine":"openviking"},"plugins":[{"id":"memory-core","kind":"memory","enabled":true,"selected":true,"slot":"memory"},{"id":"openviking","kind":"context-engine","enabled":true,"selected":true,"slot":"contextEngine"}]}')
        if 'inspect memory-core' in command:
            return CP('{"id":"memory-core","kind":"memory","enabled":true,"slot":"memory"}')
        if 'inspect openviking' in command:
            return CP('{"id":"openviking","kind":"context-engine","enabled":true,"slot":"contextEngine"}')
        raise AssertionError(command)

    monkeypatch.setattr(cgs, 'run_shell', fake_run_shell)
    run_root = tmp_path / 'run'
    run_root.mkdir(parents=True)
    snapshot = cgs.capture_group_snapshot('row4-compat-primary', 'snap-unit', run_root)
    assert snapshot['plugin_inventory']['normalized']['inventory_selected_slots']['contextEngine'] == 'openviking'
    assert snapshot['runtime_architecture']['overall_passed'] is True
    assert (run_root / 'config_snapshot.json').exists()


def test_finalize_marks_runtime_architecture_failure_invalid() -> None:
    group = 'row4-compat-primary'
    run_id = 'unit-finalize-invalid'
    root_path = ROOT / 'runs' / 'smoke' / run_id / group / 'micro'
    sample_root = root_path / 'sample_0'
    sample_root.mkdir(parents=True, exist_ok=True)

    write_json(root_path / 'run_spec.json', {'group': group, 'run_id': run_id, 'mode': 'smoke', 'stage': 'micro'})
    write_json(
        root_path / 'run_meta.json',
        {
            'samples': [
                {
                    'sample_idx': 0,
                    'ingest_user': 'u',
                    'qa_user': 'u',
                    'ingest_command': ['python', 'eval.py', 'ingest'],
                    'qa_command': ['python', 'eval.py', 'qa', '-p', '1'],
                }
            ]
        },
    )
    write_json(sample_root / 'ingest.txt.json', [{'session': 's0', 'usage': {'input_tokens': 10}}])
    qa_lines = [json.dumps({'qi': i, 'question': f'q{i}', 'expected': 'a', 'response': 'a', 'category': 1, 'usage': {'input_tokens': 1}}) for i in range(10)]
    (sample_root / 'qa_records.jsonl').write_text('\n'.join(qa_lines) + '\n', encoding='utf-8')
    write_json(
        root_path / 'config_snapshot.json',
        {
            'openclaw': {'actual_snapshot': 'x', 'comparison': {'actual_json_parsed': True, 'structural_subset_match': True, 'exact_subset_match': True}},
            'openviking': {'actual_snapshot': 'y', 'comparison': {'actual_json_parsed': True, 'structural_subset_match': True, 'exact_subset_match': True}},
            'plugin_inventory': {'list_returncode': 0, 'inspect_outputs': []},
            'runtime_architecture': {'overall_passed': False, 'blocking_reasons': ['row4 failed'], 'checks': {'row4_coexistence_proved': False}},
        },
    )
    write_json(root_path / 'config_drift.json', {'drift_detected': False, 'drift_reasons': []})

    finalize_group.summarize(group, run_id, 'smoke', 'micro')
    summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
    assert summary['pipeline_status'] == 'invalid'
    assert 'runtime architecture proof failed or missing' in summary['invalidity_reasons']
    assert 'row4 runtime did not prove memory-core + contextEngine=openviking coexistence' in summary['invalidity_reasons']
