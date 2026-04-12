from __future__ import annotations

from pathlib import Path

import pytest

import run_eval_group as reg
from materialize_configs import materialize
from _common import load_env_file, load_json, write_json


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


def test_materialize_exports_run_isolated_openclaw_home_and_state_dirs(monkeypatch, tmp_path: Path) -> None:
    _set_row2_env(monkeypatch)

    materialize('row2-memory-lancedb', 'unit-state', tmp_path)

    runtime_dir = tmp_path / 'unit-state' / 'row2-memory-lancedb'
    exports = load_env_file(runtime_dir / 'exports.env')
    manifest = load_json(runtime_dir / 'materialization_manifest.json')

    home = Path(exports['OPENCLAW_HOME']).resolve()
    state_dir = Path(exports['OPENCLAW_STATE_DIR']).resolve()

    assert home.name == 'openclaw-home'
    assert state_dir.name == 'openclaw-state'

    assert home.parent.name == 'row2-memory-lancedb'
    assert state_dir.parent.name == 'row2-memory-lancedb'
    assert home.parent.parent.name == 'unit-state'
    assert state_dir.parent.parent.name == 'unit-state'
    assert home.parent.parent.parent.name == 'storage'
    assert state_dir.parent.parent.parent.name == 'storage'

    assert home.exists() and home.is_dir()
    assert state_dir.exists() and state_dir.is_dir()

    assert exports['OPENCLAW_HOME'] == str(home)
    assert exports['OPENCLAW_STATE_DIR'] == str(state_dir)
    assert manifest['materialized_exports']['OPENCLAW_HOME'] == str(home)
    assert manifest['materialized_exports']['OPENCLAW_STATE_DIR'] == str(state_dir)
    assert manifest['runtime_isolation']['openclaw_home'] == str(home)
    assert manifest['runtime_isolation']['openclaw_state_dir'] == str(state_dir)


@pytest.mark.parametrize(
    ('env_key', 'runtime_key', 'leaf'),
    [
        ('OPENCLAW_HOME', 'openclaw_home', 'openclaw-home'),
        ('OPENCLAW_STATE_DIR', 'openclaw_state_dir', 'openclaw-state'),
    ],
)
def test_assert_materialization_binding_rejects_openclaw_isolation_dir_escape(
    monkeypatch,
    tmp_path: Path,
    env_key: str,
    runtime_key: str,
    leaf: str,
) -> None:
    _set_row2_env(monkeypatch)

    materialize('row2-memory-lancedb', 'unit-state-escape', tmp_path)

    runtime_dir = tmp_path / 'unit-state-escape' / 'row2-memory-lancedb'
    exports = load_env_file(runtime_dir / 'exports.env')
    manifest_path = Path(exports['REPRO_MATERIALIZATION_MANIFEST'])
    manifest = load_json(manifest_path)

    escape_path = (tmp_path / 'escape' / leaf).resolve()
    escape_path.mkdir(parents=True, exist_ok=True)

    exports[env_key] = str(escape_path)
    manifest['materialized_exports'][env_key] = str(escape_path)
    manifest.setdefault('runtime_isolation', {})[runtime_key] = str(escape_path)
    write_json(manifest_path, manifest)

    with pytest.raises(SystemExit) as exc:
        reg._assert_materialization_binding('row2-memory-lancedb', 'unit-state-escape', exports)

    message = str(exc.value)
    assert env_key in message