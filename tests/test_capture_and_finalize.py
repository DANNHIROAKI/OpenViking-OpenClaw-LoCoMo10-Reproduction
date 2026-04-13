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


def test_capture_snapshot_redacts_public_and_persists_private_raw(monkeypatch, tmp_path: Path) -> None:
    oc_path = tmp_path / 'openclaw.json'
    write_json(
        oc_path,
        {
            'plugins': {
                'slots': {'memory': 'memory-lancedb', 'contextEngine': 'legacy'},
                'entries': {
                    'memory-lancedb': {
                        'config': {
                            'embedding': {
                                'apiKey': 'secret-key',
                                'model': 'text-embedding-3-large',
                            }
                        }
                    }
                },
            }
        },
    )
    monkeypatch.setenv('OPENCLAW_CONFIG_PATH', str(oc_path))
    monkeypatch.delenv('OPENVIKING_CONFIG_PATH', raising=False)

    def fake_run_shell(command: str, **kwargs):
        class CP:
            def __init__(self, stdout: str):
                self.stdout = stdout
                self.stderr = ''
                self.returncode = 0

        if 'plugins list' in command:
            return CP('{"slots":{"memory":"memory-lancedb","contextEngine":"legacy"},"plugins":[{"id":"memory-lancedb","kind":"memory","enabled":true,"selected":true,"slot":"memory"}]}')
        if 'inspect memory-lancedb' in command:
            return CP('{"id":"memory-lancedb","kind":"memory","enabled":true,"slot":"memory"}')
        raise AssertionError(command)

    monkeypatch.setattr(cgs, 'run_shell', fake_run_shell)
    monkeypatch.setattr(cgs, 'ROOT', tmp_path)

    run_root = tmp_path / 'runs' / 'smoke' / 'snap-redact' / 'row2-memory-lancedb' / 'micro'
    run_root.mkdir(parents=True, exist_ok=True)

    snapshot = cgs.capture_group_snapshot('row2-memory-lancedb', 'snap-redact', run_root)

    public_path = Path(snapshot['openclaw']['actual_snapshot_public'])
    private_path = Path(snapshot['openclaw']['actual_snapshot_private'])

    assert public_path.exists()
    assert private_path.exists()
    assert 'private_snapshots' in private_path.parts
    assert 'private_snapshots' not in public_path.parts

    public_payload = json.loads(public_path.read_text(encoding='utf-8'))
    private_payload = json.loads(private_path.read_text(encoding='utf-8'))

    assert public_payload['plugins']['entries']['memory-lancedb']['config']['embedding']['apiKey'] == '[REDACTED]'
    assert private_payload['plugins']['entries']['memory-lancedb']['config']['embedding']['apiKey'] == 'secret-key'
    assert snapshot['openclaw']['redaction_applied'] is True
    assert 'plugins.entries.memory-lancedb.config.embedding.apiKey' in snapshot['openclaw']['redacted_paths']


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
            'openclaw': {
                'actual_snapshot_public': 'x',
                'actual_snapshot_private': 'y',
                'comparison': {'actual_json_parsed': True, 'structural_subset_match': True, 'exact_subset_match': True},
                'redaction_applied': True,
                'redacted_paths': ['plugins.entries.memory-lancedb.config.embedding.apiKey'],
            },
            'openviking': {
                'actual_snapshot_public': 'z',
                'actual_snapshot_private': 'w',
                'comparison': {'actual_json_parsed': True, 'structural_subset_match': True, 'exact_subset_match': True},
                'redaction_applied': False,
                'redacted_paths': [],
            },
            'plugin_inventory': {'list_returncode': 0, 'inspect_outputs': []},
            'runtime_architecture': {
                'overall_passed': runtime_arch_passed,
                'blocking_reasons': [] if runtime_arch_passed else ['row4 failed'],
                'checks': {'row4_coexistence_proved': runtime_arch_passed},
            },
            'runtime_audit_freeze': {
                'row2-memory-lancedb': {
                    'lancedb_embedding_provider': 'openai-compatible',
                }
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


def test_finalize_extended_smoke_requires_precise_case_count(monkeypatch, tmp_path: Path) -> None:
    benchmark_dir = tmp_path / 'benchmark'
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        benchmark_dir / 'manifest.json',
        {
            'filtered_total_qas': 1540,
            'per_sample_filtered_qas': {
                '0': 123,
                '1': 110,
            },
        },
    )
    monkeypatch.setattr(finalize_group, 'ROOT', tmp_path)

    run_id = 'unit-extended-count'
    group = 'row1-memory-core'
    root_path = tmp_path / 'runs' / 'smoke' / run_id / group / 'extended'
    sample0 = root_path / 'sample_0'
    sample1 = root_path / 'sample_1'
    sample0.mkdir(parents=True, exist_ok=True)
    sample1.mkdir(parents=True, exist_ok=True)

    write_json(
        root_path / 'run_spec.json',
        {
            'group': group,
            'run_id': run_id,
            'mode': 'smoke',
            'stage': 'extended',
            'tail_literal': TAIL_LITERAL,
            'parallel': PARALLEL,
            'gateway_only': True,
            'forbid_eval_viking_flag': True,
        },
    )
    write_json(
        root_path / 'run_meta.json',
        {
            'samples': [
                {
                    'sample_idx': 0,
                    'ingest_user': user_id(run_id, group, 0),
                    'qa_user': user_id(run_id, group, 0),
                    'ingest_command': ['python', 'eval.py', 'ingest', '--user', user_id(run_id, group, 0), '--tail', TAIL_LITERAL],
                    'qa_command': ['python', 'eval.py', 'qa', '--user', user_id(run_id, group, 0), '-p', '1'],
                },
                {
                    'sample_idx': 1,
                    'ingest_user': user_id(run_id, group, 1),
                    'qa_user': user_id(run_id, group, 1),
                    'ingest_command': ['python', 'eval.py', 'ingest', '--user', user_id(run_id, group, 1), '--tail', TAIL_LITERAL],
                    'qa_command': ['python', 'eval.py', 'qa', '--user', user_id(run_id, group, 1), '-p', '1'],
                },
            ]
        },
    )
    write_json(sample0 / 'ingest.txt.json', [{'session': 's0', 'usage': {'input_tokens': 10}}])
    write_json(sample1 / 'ingest.txt.json', [{'session': 's1', 'usage': {'input_tokens': 10}}])

    qa_lines_0 = [
        json.dumps({'qi': i, 'question': f'q{i}', 'expected': 'a', 'response': 'a', 'category': 1, 'usage': {'input_tokens': 1}})
        for i in range(100)
    ]
    qa_lines_1 = [
        json.dumps({'qi': i, 'question': f'q{i}', 'expected': 'a', 'response': 'a', 'category': 1, 'usage': {'input_tokens': 1}})
        for i in range(100)
    ]
    (sample0 / 'qa_records.jsonl').write_text('\n'.join(qa_lines_0) + '\n', encoding='utf-8')
    (sample1 / 'qa_records.jsonl').write_text('\n'.join(qa_lines_1) + '\n', encoding='utf-8')

    write_json(
        root_path / 'config_snapshot.json',
        {
            'openclaw': {
                'actual_snapshot_public': 'x',
                'actual_snapshot_private': 'y',
                'comparison': {'actual_json_parsed': True, 'structural_subset_match': True, 'exact_subset_match': True},
                'redaction_applied': False,
                'redacted_paths': [],
            },
            'plugin_inventory': {'list_returncode': 0, 'inspect_outputs': []},
            'runtime_architecture': {'overall_passed': True, 'blocking_reasons': [], 'checks': {}},
            'runtime_audit_freeze': {},
        },
    )
    write_json(root_path / 'config_drift.json', {'drift_detected': False, 'drift_reasons': []})

    finalize_group.summarize(group, run_id, 'smoke', 'extended')
    summary = json.loads((root_path / 'run_summary.json').read_text(encoding='utf-8'))
    assert summary['pipeline_status'] == 'invalid'
    assert 'extended smoke result count mismatched expected filtered QA count for samples 0 and 1' in summary['invalidity_reasons']