from __future__ import annotations

from pathlib import Path

import freeze_versions
from _common import load_json, write_json


def _set_formal_model_env(monkeypatch) -> None:
    env = {
        'OPENCLAW_MODEL_PROVIDER': 'openai-compatible',
        'OPENCLAW_MODEL_API_BASE': 'https://example.com/v1',
        'OPENCLAW_MODEL_DEPLOYMENT_ID': 'seed-2.0-code-prod',
        'OPENCLAW_MODEL_ID': 'seed-2.0-code',
        'OPENCLAW_MODEL_TEMPERATURE': '0',
        'OPENCLAW_MODEL_MAX_TOKENS': '4096',
        'OPENCLAW_MODEL_REASONING': 'medium',
        'JUDGE_MODEL': 'gpt-4o-mini',
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


def _prepare_fake_host(monkeypatch, tmp_path: Path) -> Path:
    manifest_path = tmp_path / 'env' / 'versions_manifest.json'
    write_json(manifest_path, {'capture_status': 'placeholder'})

    judge_py = tmp_path / 'vendor' / 'judge.py'
    judge_util_py = tmp_path / 'vendor' / 'judge_util.py'
    install_manifest = tmp_path / 'vendor' / 'install-manifest.json'

    judge_py.parent.mkdir(parents=True, exist_ok=True)
    judge_py.write_text('# judge\n', encoding='utf-8')
    judge_util_py.write_text('# judge util\n', encoding='utf-8')
    write_json(
        install_manifest,
        {
            'compatibility': {
                'minOpenvikingVersion': '0.2.9',
                'minOpenclawVersion': '2026.3.7',
            }
        },
    )

    monkeypatch.setattr(freeze_versions, 'ROOT', tmp_path)
    monkeypatch.setattr(freeze_versions, 'JUDGE_PY', judge_py)
    monkeypatch.setattr(freeze_versions, 'JUDGE_UTIL_PY', judge_util_py)
    monkeypatch.setattr(freeze_versions, 'CONTEXT_INSTALL_MANIFEST', install_manifest)
    monkeypatch.setattr(freeze_versions, 'apply_env_file', lambda: None)

    def fake_cmd_text(cmd: list[str]) -> str | None:
        if cmd == ['openclaw', '--version']:
            return '2026.3.11'
        if cmd == ['node', '-v']:
            return 'v22.4.0'
        if cmd == ['python3', '--version']:
            return 'Python 3.11.8'
        if len(cmd) >= 2 and cmd[1] == '-c':
            return '0.1.18'
        raise AssertionError(f'unexpected command: {cmd!r}')

    monkeypatch.setattr(freeze_versions, 'cmd_text', fake_cmd_text)
    return manifest_path


def test_model_route_block_requires_temperature_max_tokens_and_reasoning(monkeypatch) -> None:
    monkeypatch.setenv('OPENCLAW_MODEL_PROVIDER', 'openai-compatible')
    monkeypatch.setenv('OPENCLAW_MODEL_API_BASE', 'https://example.com/v1')
    monkeypatch.setenv('OPENCLAW_MODEL_DEPLOYMENT_ID', 'seed-2.0-code-prod')
    monkeypatch.setenv('OPENCLAW_MODEL_ID', 'seed-2.0-code')
    monkeypatch.delenv('OPENCLAW_MODEL_TEMPERATURE', raising=False)
    monkeypatch.delenv('OPENCLAW_MODEL_MAX_TOKENS', raising=False)
    monkeypatch.delenv('OPENCLAW_MODEL_REASONING', raising=False)

    block = freeze_versions._model_route_block()

    assert block['required_fields'] == [
        'provider',
        'api_base',
        'deployment_or_endpoint_id',
        'model',
        'temperature',
        'max_tokens',
        'reasoning',
    ]
    assert block['missing_required_fields'] == ['temperature', 'max_tokens', 'reasoning']
    assert block['complete_for_formal_runs'] is False

    readiness = freeze_versions._build_group_readiness(
        observed={
            'openclaw': '2026.3.11',
            'node': 'v22.4.0',
            'python': 'Python 3.11.8',
            'openviking_runtime': '0.1.18',
        },
        model_route=block,
        plugin_runtime_constraints={
            'row4_context_engine_snapshot_min_openviking_version': '0.2.9',
            'row4_context_engine_snapshot_min_openclaw_version': '2026.3.7',
        },
    )

    row1 = readiness['row1-memory-core']
    row2 = readiness['row2-memory-lancedb']

    assert row1['ready_for_formal_wrapper'] is False
    assert row2['ready_for_formal_wrapper'] is False
    assert any('temperature' in reason for reason in row1['blocking_reasons'])
    assert any('max_tokens' in reason for reason in row2['blocking_reasons'])
    assert any('reasoning' in reason for reason in row2['blocking_reasons'])


def test_main_writes_row2_group_specific_runtime_freeze(monkeypatch, tmp_path: Path) -> None:
    _set_formal_model_env(monkeypatch)
    _set_row2_env(monkeypatch)
    manifest_path = _prepare_fake_host(monkeypatch, tmp_path)

    freeze_versions.main()

    manifest = load_json(manifest_path)

    assert manifest['capture_status'] == 'captured'
    assert manifest['resolved_model_freeze']['required_fields'] == [
        'provider',
        'api_base',
        'deployment_or_endpoint_id',
        'model',
        'temperature',
        'max_tokens',
        'reasoning',
    ]
    assert manifest['resolved_model_freeze']['missing_required_fields'] == []
    assert manifest['group_readiness']['row2-memory-lancedb']['ready_for_formal_wrapper'] is True

    row2 = manifest['group_specific_runtime_freeze']['row2-memory-lancedb']
    assert row2 == {
        'lancedb_embedding_provider': 'openai-compatible',
        'lancedb_embedding_model': 'text-embedding-3-large',
        'lancedb_embedding_api_base': 'https://example.com/v1',
        'lancedb_embedding_dimension': '3072',
    }
    assert 'lancedb_embedding_api_key' not in row2