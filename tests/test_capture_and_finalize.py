from __future__ import annotations

import json
import shutil
from pathlib import Path

import capture_group_snapshot as cgs
import finalize_group
from _common import PARALLEL, ROOT, TAIL_LITERAL, user_id, write_json



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



def _make_sample_root(group: str, run_id: str, *, stage: str = 'micro') -> Path:
    root_path = ROOT / 'runs' / 'smoke' / run_id / group / stage
    if root_path.exists():
        shutil.rmtree(root_path)
    (root_path / 'sample_0').mkdir(parents=True, exist_ok=False)
    return root_path



def _write_minimal_finalize_fixture(
    group: str,
    run_id: str,
    *,
    tail_values: list[str] | None = None,
    ingest_user: str | None = None,
    qa_user: str | None = None,
    run_spec_tail: str = TAIL_LITERAL,
    run_spec_parallel: int = PARALLEL,
    gateway_only: bool = True,
    forbid_eval_viking_flag: bool = True,
    runtime_arch_passed: bool = True,
) -> Path:
    root_path = _make_sample_root(group, run_id)
    sample_root = root_path / 'sample_0'
    expected_user = user_id(run_id, group, 0)
    ingest_user = ingest_user or expected_user
    qa_user = qa_user or expected_user
    tail_values = tail_values if tail_values is not None else [TAIL_LITERAL]

    ingest_command = ['python', 'eval.py', 'ingest', '--user', ingest_user]
    if tail_values is not None:
        for tail in tail_values:
            ingest_command.extend(['--tail', tail])
    qa_command = ['python', 'eval.py', 'qa', '--user', qa_user, '-p', '1']

    write_json(
        root_path / 'run_spec.json',
        {
            'group': group,
            'run_id': run_id,
            'mode': 'smoke',
            'stage': 'micro',
            'tail_literal': run_spec_tail,
            'parallel': run_spec_parallel,
            'gateway_only': gateway_only,
            'forbid_eval_viking_flag': forbid_eval_viking_flag,
        },
    )
    write_json(
        root_path / 'run_meta.json',
        {
            'samples': [
                {
                    'sample_idx': 0,
                    'ingest_user': ingest_user,
                    'qa_user': qa_user,
                    'ingest_command': ingest_command,
                    'qa_command': qa_command,
                }
            ]
        },
    )
    write_json(sample_root / 'ingest.txt.json', [{'session': 's0', 'usage': {'input_tokens': 10}}])
    qa_lines = [
        json.dumps({'qi': i, 'question': f'q{i}', 'expected': 'a', 'response': 'a', 'category': 1, 'usage': {'input_tokens': 1}})
        for i in range(10)
    ]
    (sample_root / 'qa_records.jsonl').write_text('\n'.join(qa_lines) + '\n', encoding='utf-8')
    write_json(
        root_path / 'config_snapshot.json',
        {
            'openclaw': {'actual_snapshot': 'x', 'comparison': {'actual_json_parsed': True, 'structural_subset_match': True, 'exact_subset_match': True}},
            'openviking': {'actual_snapshot': 'y', 'comparison': {'actual_json_parsed': True, 'structural_subset_match': True, 'exact_subset_match': True}},
            'plugin_inventory': {'list_returncode': 0, 'inspect_outputs': []},
            'runtime_architecture': {
                'overall_passed': runtime_arch_passed,
                'blocking_reasons': [] if runtime_arch_passed else ['row4 failed'],
                'checks': {'row4_coexistence_proved': runtime_arch_passed},
            },
        },
    )
    write_json(root_path / 'config_drift.json', {'drift_detected': False, 'drift_reasons': []})
    return root_path



def test_finalize_marks_runtime_architecture_failure_invalid() -> None:
    group = 'row4-compat-primary'
    run_id = 'unit-finalize-invalid'
    root_path = _write_minimal_finalize_fixture(group, run_id, runtime_arch_passed=False)

    finalize_group.summarize(group, run_id, 'smoke', 'micro')
    summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
    assert summary['pipeline_status'] == 'invalid'
    assert 'runtime architecture proof failed or missing' in summary['invalidity_reasons']
    assert 'row4 runtime did not prove memory-core + contextEngine=openviking coexistence' in summary['invalidity_reasons']



def test_finalize_accepts_frozen_tail_and_user_pattern() -> None:
    group = 'row1-memory-core'
    run_id = 'unit-finalize-good'
    root_path = _write_minimal_finalize_fixture(group, run_id)

    finalize_group.summarize(group, run_id, 'smoke', 'micro')
    summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
    assert summary['pipeline_status'] == 'valid'



def test_finalize_rejects_missing_tail() -> None:
    group = 'row1-memory-core'
    run_id = 'unit-finalize-missing-tail'
    root_path = _write_minimal_finalize_fixture(group, run_id, tail_values=[])

    finalize_group.summarize(group, run_id, 'smoke', 'micro')
    summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
    assert 'ingest command missing required --tail' in summary['invalidity_reasons']



def test_finalize_rejects_wrong_tail_literal() -> None:
    group = 'row1-memory-core'
    run_id = 'unit-finalize-wrong-tail'
    root_path = _write_minimal_finalize_fixture(group, run_id, tail_values=['[]'])

    finalize_group.summarize(group, run_id, 'smoke', 'micro')
    summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
    assert 'ingest command tail literal drifted from frozen spec' in summary['invalidity_reasons']



def test_finalize_rejects_user_pattern_drift() -> None:
    group = 'row1-memory-core'
    run_id = 'unit-finalize-user-drift'
    root_path = _write_minimal_finalize_fixture(group, run_id, ingest_user='u', qa_user='u')

    finalize_group.summarize(group, run_id, 'smoke', 'micro')
    summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
    assert 'sample user id drifted from frozen user pattern' in summary['invalidity_reasons']



def test_finalize_rejects_run_spec_parallel_drift() -> None:
    group = 'row1-memory-core'
    run_id = 'unit-finalize-parallel-drift'
    root_path = _write_minimal_finalize_fixture(group, run_id, run_spec_parallel=2)

    finalize_group.summarize(group, run_id, 'smoke', 'micro')
    summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
    assert 'run_spec parallel drifted from frozen group definition' in summary['invalidity_reasons']
