from __future__ import annotations

from pathlib import Path

import _common


def test_load_env_file_supports_export_and_quotes(tmp_path: Path) -> None:
    env_file = tmp_path / '.env'
    env_file.write_text("export A=1\nB='two words'\nC=\"three\"\n# comment\n", encoding='utf-8')
    loaded = _common.load_env_file(env_file)
    assert loaded == {'A': '1', 'B': 'two words', 'C': 'three'}


def test_merged_env_prefers_shell_over_dotenv(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / '.env'
    env_file.write_text('KEY=from_dotenv\n', encoding='utf-8')
    monkeypatch.setattr(_common, 'ENV_FILE', env_file)
    monkeypatch.delenv('REPRO_RUNTIME_ENV_FILE', raising=False)
    env = _common.merged_env(base_env={'KEY': 'from_shell'})
    assert env['KEY'] == 'from_shell'


def test_extra_overrides_shell(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / '.env'
    env_file.write_text('KEY=from_dotenv\n', encoding='utf-8')
    monkeypatch.setattr(_common, 'ENV_FILE', env_file)
    env = _common.merged_env({'KEY': 'from_extra'}, base_env={'KEY': 'from_shell'})
    assert env['KEY'] == 'from_extra'


def test_sensitive_values_are_not_coerced() -> None:
    value = {
        'api_key': '12345',
        'token': '67890',
        'port': '8080',
        'flag': 'true',
        'items': '[1, 2]'
    }
    out = _common.coerce_non_sensitive_scalars(value)
    assert out['api_key'] == '12345'
    assert out['token'] == '67890'
    assert out['port'] == 8080
    assert out['flag'] is True
    assert out['items'] == [1, 2]
