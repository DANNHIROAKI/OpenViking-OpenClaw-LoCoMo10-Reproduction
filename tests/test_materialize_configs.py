from __future__ import annotations

from pathlib import Path

import pytest

import run_eval_group as reg
from materialize_configs import materialize
from _common import load_env_file, load_json



def _set_row4_env(monkeypatch) -> None:
    env = {
        'OPENVIKING_SERVER_HOST': '127.0.0.1',
        'OPENVIKING_SERVER_PORT': '8080',
        'OPENVIKING_LOG_LEVEL': 'info',
        'OPENVIKING_LOG_OUTPUT': '/tmp/ov-test.log',
        'OPENVIKING_VLM_PROVIDER': 'openai-compatible',
        'OPENVIKING_VLM_API_KEY': 'vk',
        'OPENVIKING_VLM_MODEL': 'gpt-4.1-mini',
        'OPENVIKING_VLM_API_BASE': 'https://example.com/v1',
        'OPENVIKING_EMBEDDING_PROVIDER': 'openai-compatible',
        'OPENVIKING_EMBEDDING_API_KEY': 'ek',
        'OPENVIKING_EMBEDDING_MODEL': 'text-embedding-3-large',
        'OPENVIKING_EMBEDDING_API_BASE': 'https://example.com/v1',
        'OPENVIKING_EMBEDDING_DIMENSION': '3072',
        'OPENVIKING_DIAGNOSTIC_ENDPOINT': 'http://127.0.0.1:1933/metrics',
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)



def _set_row2_env(monkeypatch) -> None:
    env = {
        'LANCEDB_EMBEDDING_PROVIDER': 'openai-compatible',
        'LANCEDB_EMBEDDING_API_KEY': 'lk',
        'LANCEDB_EMBEDDING_API_BASE': 'https://example.com/v1',
        'LANCEDB_EMBEDDING_MODEL': 'text-embedding-3-large',
        'LANCEDB_EMBEDDING_DIMENSION': '3072',
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)



def test_materialize_writes_exports_and_coerces_types(monkeypatch, tmp_path: Path) -> None:
    _set_row4_env(monkeypatch)
    out = materialize('row4-compat-primary', 'unit-row4', tmp_path)
    runtime_dir = tmp_path / 'unit-row4' / 'row4-compat-primary'
    ov_cfg = load_json(runtime_dir / 'ov.conf')
    oc_cfg = load_json(runtime_dir / 'openclaw.json')
    exports_text = (runtime_dir / 'exports.env').read_text(encoding='utf-8')
    manifest = load_json(runtime_dir / 'materialization_manifest.json')

    assert ov_cfg['server']['port'] == 8080
    assert oc_cfg['plugins']['entries']['openviking']['config']['recallPreferAbstract'] is False
    assert 'OPENCLAW_CONFIG_PATH=' in exports_text
    assert 'OPENVIKING_HEALTH_URL=' in exports_text
    assert 'OPENVIKING_LOG_FILE=' in exports_text
    assert 'OPENVIKING_WORKSPACE_PATH=' in exports_text
    assert 'REPRO_RUNTIME_ENV_FILE=' in exports_text
    assert 'REPRO_MATERIALIZATION_MANIFEST=' in exports_text
    assert out['materialized_exports']['OPENVIKING_LOG_FILE'] == '/tmp/ov-test.log'
    assert out['materialized_exports']['OPENVIKING_DIAGNOSTIC_ENDPOINT'] == 'http://127.0.0.1:1933/metrics'
    assert manifest['materialization_mode'] == 'fresh'
    assert manifest['openviking_workspace_path'].endswith('storage/unit-row4/row4-compat-primary/openviking-workspace')



def test_materialize_overrides_stale_shell_config_paths(monkeypatch, tmp_path: Path) -> None:
    _set_row2_env(monkeypatch)
    monkeypatch.setenv('OPENCLAW_CONFIG_PATH', '/stale/config.json')
    out = materialize('row2-memory-lancedb', 'unit-row2', tmp_path)
    expected = str((tmp_path / 'unit-row2' / 'row2-memory-lancedb' / 'openclaw.json').resolve())
    assert out['materialized_exports']['OPENCLAW_CONFIG_PATH'] == expected



def test_materialize_rejects_existing_target_without_force(monkeypatch, tmp_path: Path) -> None:
    _set_row2_env(monkeypatch)
    materialize('row2-memory-lancedb', 'unit-reject', tmp_path)
    with pytest.raises(SystemExit) as exc:
        materialize('row2-memory-lancedb', 'unit-reject', tmp_path)
    assert 'runtime config dir already exists' in str(exc.value)



def test_materialize_force_moves_old_target_to_backup(monkeypatch, tmp_path: Path) -> None:
    _set_row2_env(monkeypatch)
    runtime_dir = tmp_path / 'unit-force' / 'row2-memory-lancedb'
    materialize('row2-memory-lancedb', 'unit-force', tmp_path)
    original_manifest = load_json(runtime_dir / 'materialization_manifest.json')
    monkeypatch.setenv('LANCEDB_EMBEDDING_MODEL', 'text-embedding-3-small')

    materialize('row2-memory-lancedb', 'unit-force', tmp_path, force=True)
    replaced_roots = list((tmp_path / '_replaced').glob('*'))
    assert replaced_roots, 'expected a backup directory under _replaced/'
    backed_up_manifest = list((tmp_path / '_replaced').glob('*/unit-force/row2-memory-lancedb/materialization_manifest.json'))
    assert len(backed_up_manifest) == 1
    assert load_json(backed_up_manifest[0])['materialization_mode'] == original_manifest['materialization_mode']
    assert load_json(runtime_dir / 'materialization_manifest.json')['materialization_mode'] == 'force-replaced'



def test_run_eval_group_requires_bound_materialization_manifest(monkeypatch, tmp_path: Path) -> None:
    _set_row4_env(monkeypatch)
    materialize('row4-compat-primary', 'unit-bind', tmp_path)
    exports = load_env_file(tmp_path / 'unit-bind' / 'row4-compat-primary' / 'exports.env')
    binding = reg._assert_materialization_binding('row4-compat-primary', 'unit-bind', exports)
    assert binding['materialization_manifest'].endswith('materialization_manifest.json')
    assert binding['materialization_dir'].endswith('/unit-bind/row4-compat-primary')
