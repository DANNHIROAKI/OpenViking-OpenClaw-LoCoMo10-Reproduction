from __future__ import annotations

from pathlib import Path

from materialize_configs import materialize
from _common import ROOT, load_json


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
    ov_cfg = load_json(tmp_path / 'unit-row4' / 'row4-compat-primary' / 'ov.conf')
    oc_cfg = load_json(tmp_path / 'unit-row4' / 'row4-compat-primary' / 'openclaw.json')
    exports_text = (tmp_path / 'unit-row4' / 'row4-compat-primary' / 'exports.env').read_text(encoding='utf-8')

    assert ov_cfg['server']['port'] == 8080
    assert oc_cfg['plugins']['entries']['openviking']['config']['recallPreferAbstract'] is False
    assert 'OPENCLAW_CONFIG_PATH=' in exports_text
    assert 'OPENVIKING_HEALTH_URL=' in exports_text
    assert 'OPENVIKING_LOG_FILE=' in exports_text
    assert out['materialized_exports']['OPENVIKING_LOG_FILE'] == '/tmp/ov-test.log'


def test_materialize_overrides_stale_shell_config_paths(monkeypatch, tmp_path: Path) -> None:
    _set_row2_env(monkeypatch)
    monkeypatch.setenv('OPENCLAW_CONFIG_PATH', '/stale/config.json')
    out = materialize('row2-memory-lancedb', 'unit-row2', tmp_path)
    expected = str((tmp_path / 'unit-row2' / 'row2-memory-lancedb' / 'openclaw.json').resolve())
    assert out['materialized_exports']['OPENCLAW_CONFIG_PATH'] == expected
