from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import (
    BENCHMARK_MANIFEST_PATH,
    CLAIM_DECISIONS_PATH,
    GROUP_DEFS_PATH,
    OPENCLAW_EVAL_DIR,
    ROOT,
    apply_env_file,
    collect_env_placeholders,
    get_group_spec,
    group_readiness,
    load_json,
    missing_env_vars,
    merged_env,
    render_placeholders,
    sha256_file,
)

OPENCLAW_TEMPLATES = ROOT / 'env/openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env/openviking_config_templates'
PUBLIC_EVIDENCE_MANIFEST = ROOT / 'env/public_evidence_manifest.json'
VERSIONS_MANIFEST = ROOT / 'env/versions_manifest.json'
SOURCE_MANIFEST = ROOT / 'env/source_manifest.json'
OFFICIAL_TARGETS = ROOT / 'official_targets.json'

ROW3_ALLOWED = {
    'mode',
    'configPath',
    'port',
    'baseUrl',
    'agentId',
    'apiKey',
    'targetUri',
    'timeoutMs',
    'autoCapture',
    'captureMode',
    'captureMaxLength',
    'autoRecall',
    'recallLimit',
    'recallScoreThreshold',
    'ingestReplyAssist',
    'ingestReplyAssistMinSpeakerTurns',
    'ingestReplyAssistMinChars',
}
ROW3_REQUIRED = {
    'mode',
    'configPath',
    'port',
    'agentId',
    'targetUri',
    'timeoutMs',
    'autoCapture',
    'captureMode',
    'captureMaxLength',
    'autoRecall',
    'recallLimit',
    'recallScoreThreshold',
    'ingestReplyAssist',
    'ingestReplyAssistMinSpeakerTurns',
    'ingestReplyAssistMinChars',
}
ROW4_ALLOWED = {
    'mode',
    'configPath',
    'port',
    'baseUrl',
    'agentId',
    'apiKey',
    'targetUri',
    'timeoutMs',
    'autoCapture',
    'captureMode',
    'captureMaxLength',
    'autoRecall',
    'recallLimit',
    'recallScoreThreshold',
    'recallMaxContentChars',
    'recallPreferAbstract',
    'recallTokenBudget',
    'commitTokenThreshold',
    'bypassSessionPatterns',
    'ingestReplyAssist',
    'ingestReplyAssistMinSpeakerTurns',
    'ingestReplyAssistMinChars',
    'ingestReplyAssistIgnoreSessionPatterns',
    'emitStandardDiagnostics',
    'logFindRequests',
}
ROW4_REQUIRED = {
    'mode',
    'configPath',
    'port',
    'agentId',
    'targetUri',
    'timeoutMs',
    'autoCapture',
    'captureMode',
    'captureMaxLength',
    'autoRecall',
    'recallLimit',
    'recallScoreThreshold',
    'recallMaxContentChars',
    'recallPreferAbstract',
    'recallTokenBudget',
    'commitTokenThreshold',
    'bypassSessionPatterns',
    'ingestReplyAssist',
    'ingestReplyAssistMinSpeakerTurns',
    'ingestReplyAssistMinChars',
    'emitStandardDiagnostics',
    'logFindRequests',
}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def get_plugin_entry(template: dict, plugin_id: str) -> tuple[dict | None, dict | None]:
    entries = template.get('plugins', {}).get('entries', {})
    entry = entries.get(plugin_id)
    if not isinstance(entry, dict):
        return None, None
    cfg = entry.get('config')
    if not isinstance(cfg, dict):
        return entry, None
    return entry, cfg


def validate_repo_structure(errors: list[str], notes: list[str]) -> None:
    required = [
        GROUP_DEFS_PATH,
        CLAIM_DECISIONS_PATH,
        BENCHMARK_MANIFEST_PATH,
        SOURCE_MANIFEST,
        VERSIONS_MANIFEST,
        OFFICIAL_TARGETS,
        PUBLIC_EVIDENCE_MANIFEST,
    ]
    for path in required:
        if not path.exists():
            errors.append(f'missing required file: {rel(path)}')

    if errors:
        return

    benchmark = load_json(BENCHMARK_MANIFEST_PATH)
    if benchmark['counts']['raw_total_qas'] != 1986:
        errors.append('benchmark raw_total_qas != 1986')
    if benchmark['counts']['filtered_total_qas'] != 1540:
        errors.append('benchmark filtered_total_qas != 1540')
    if benchmark.get('byte_identical_raw_copy') is not True:
        errors.append('benchmark raw copy is not byte-identical to vendored source')

    source = benchmark['source']
    src_path = ROOT / source['path']
    if not src_path.exists():
        errors.append(f'benchmark source missing: {source["path"]}')
    else:
        actual_sha = sha256_file(src_path)
        if actual_sha != source['sha256']:
            errors.append('benchmark source sha mismatch')
        raw_copy = ROOT / benchmark['files']['locomo10_raw.json']['path']
        if raw_copy.exists() and sha256_file(raw_copy) != actual_sha:
            errors.append('benchmark raw copy sha != vendored locomo10.json sha')

    manifest = load_json(SOURCE_MANIFEST)
    for snap in manifest.get('snapshots', []):
        for file_item in snap.get('files', []):
            path = ROOT / file_item['path']
            if not path.exists():
                errors.append(f"source manifest file missing: {file_item['path']}")
                continue
            actual = sha256_file(path)
            if actual != file_item['sha256']:
                errors.append(f"sha256 mismatch: {file_item['path']}")

    versions = load_json(VERSIONS_MANIFEST)
    if versions.get('capture_status') != 'captured':
        errors.append('env/versions_manifest.json is not captured; run python3 scripts/freeze_versions.py')
    for required_group in ['row1-memory-core', 'row2-memory-lancedb', 'row3-openviking-minus-core', 'row4-compat-primary']:
        if not group_readiness(required_group, versions):
            errors.append(f'env/versions_manifest.json missing group_readiness for {required_group}')
    judge_files = versions.get('judge_freeze', {}).get('snapshot_files', {})
    for name in ['judge.py', 'judge_util.py']:
        item = judge_files.get(name, {})
        if not item.get('sha256'):
            errors.append(f'judge freeze missing sha256 for {name}')

    defs = load_json(GROUP_DEFS_PATH)
    claims = load_json(CLAIM_DECISIONS_PATH)
    official = load_json(OFFICIAL_TARGETS)
    claim_groups = {item['group'] for item in claims['decisions']}
    def_groups = {item['group'] for item in defs['groups']}
    official_groups = {item['group'] for item in official['rows']}
    if claim_groups != def_groups:
        errors.append('group_definitions.json and claim_decisions.json group sets differ')
    non_manual_groups = {item['group'] for item in defs['groups'] if not item.get('manual_only')}
    if official_groups - non_manual_groups:
        errors.append('official targets contain groups not present in non-manual group definitions')

    eval_py = (OPENCLAW_EVAL_DIR / 'eval.py').read_text(encoding='utf-8')
    if '--viking' not in eval_py:
        errors.append('vendored eval.py no longer contains --viking flag; manual re-audit required')
    if 'default="[]"' not in eval_py and "default='[]'" not in eval_py:
        errors.append('vendored eval.py tail default audit failed')
    if re.search(r'default\s*=\s*1', eval_py) is None:
        notes.append('Could not positively verify parallel default=1 by regex; inspect manually.')

    if defs['tail_literal'] != "[remember what's said, keep existing memory]":
        errors.append('tail literal drifted from frozen spec')
    if defs['parallel'] != 1:
        errors.append('parallel drifted from frozen spec')


def validate_templates(errors: list[str], notes: list[str]) -> None:
    defs = load_json(GROUP_DEFS_PATH)

    for spec in defs['groups']:
        group = spec['group']
        oc_template_path = OPENCLAW_TEMPLATES / f'{group}.json'
        ov_template_path = OPENVIKING_TEMPLATES / f'{group}.local.json'

        if not spec.get('manual_only') and not oc_template_path.exists():
            errors.append(f'missing OpenClaw template: {rel(oc_template_path)}')
        if spec.get('openviking_mode') == 'local' and not spec.get('manual_only') and not ov_template_path.exists():
            errors.append(f'missing OpenViking local template: {rel(ov_template_path)}')

    row1 = load_json(OPENCLAW_TEMPLATES / 'row1-memory-core.json')
    if row1.get('plugins', {}).get('slots', {}).get('memory') != 'memory-core':
        errors.append('row1 template memory slot != memory-core')
    if row1.get('plugins', {}).get('slots', {}).get('contextEngine') != 'legacy':
        errors.append('row1 template contextEngine slot != legacy')

    row2 = load_json(OPENCLAW_TEMPLATES / 'row2-memory-lancedb.json')
    row2_entry, row2_cfg = get_plugin_entry(row2, 'memory-lancedb')
    if row2_entry is None:
        errors.append('row2 template missing plugins.entries.memory-lancedb')
    elif row2_cfg is None:
        errors.append('row2 template must nest runtime config under plugins.entries.memory-lancedb.config')
    else:
        required = {'dbPath', 'embedding', 'autoCapture', 'autoRecall'}
        missing = required - set(row2_cfg)
        if missing:
            errors.append(f'row2 template missing keys: {sorted(missing)}')
        emb = row2_cfg.get('embedding')
        if not isinstance(emb, dict):
            errors.append('row2 template embedding must be an object')
        else:
            emb_required = {'apiKey', 'model', 'baseUrl', 'dimensions'}
            emb_missing = emb_required - set(emb)
            if emb_missing:
                errors.append(f'row2 template embedding missing keys: {sorted(emb_missing)}')

    row3 = load_json(OPENCLAW_TEMPLATES / 'row3-openviking-minus-core.json')
    row3_entry, row3_cfg = get_plugin_entry(row3, 'memory-openviking')
    if row3_entry is None:
        errors.append('row3 template missing plugins.entries.memory-openviking')
    elif row3_cfg is None:
        errors.append('row3 template must nest runtime config under plugins.entries.memory-openviking.config')
    else:
        unknown = set(row3_cfg) - ROW3_ALLOWED
        missing = ROW3_REQUIRED - set(row3_cfg)
        if unknown:
            errors.append(f'row3 template has unknown legacy plugin keys: {sorted(unknown)}')
        if missing:
            errors.append(f'row3 template missing explicit legacy plugin keys: {sorted(missing)}')
        if 'workspacePath' in row3_cfg:
            errors.append('row3 template must not contain workspacePath; workspace belongs in ov.conf')

    row4 = load_json(OPENCLAW_TEMPLATES / 'row4-compat-primary.json')
    row4_entry, row4_cfg = get_plugin_entry(row4, 'openviking')
    if row4_entry is None:
        errors.append('row4 template missing plugins.entries.openviking')
    elif row4_cfg is None:
        errors.append('row4 template must nest runtime config under plugins.entries.openviking.config')
    else:
        unknown = set(row4_cfg) - ROW4_ALLOWED
        missing = ROW4_REQUIRED - set(row4_cfg)
        if unknown:
            errors.append(f'row4 template has unknown context-engine plugin keys: {sorted(unknown)}')
        if missing:
            errors.append(f'row4 template missing explicit context-engine plugin keys: {sorted(missing)}')
        if 'workspacePath' in row4_cfg:
            errors.append('row4 template must not contain workspacePath; workspace belongs in ov.conf')

    row3_ov = load_json(OPENVIKING_TEMPLATES / 'row3-openviking-minus-core.local.json')
    if 'workspace' in row3_ov:
        errors.append('row3 OpenViking template must use storage.workspace, not workspace.root')
    storage = row3_ov.get('storage', {})
    if storage.get('workspace') != 'storage/{run_id}/{group}/openviking-workspace':
        errors.append('row3 OpenViking template storage.workspace drifted')
    if storage.get('vectordb', {}).get('backend') != 'local':
        errors.append('row3 OpenViking template must explicitly pin storage.vectordb.backend=local')
    if storage.get('agfs', {}).get('backend') != 'local':
        errors.append('row3 OpenViking template must explicitly pin storage.agfs.backend=local')
    if row3_ov.get('server', {}).get('port') is None:
        errors.append('row3 OpenViking template missing server.port')
    dense = row3_ov.get('embedding', {}).get('dense', {})
    for key in ['provider', 'api_key', 'model', 'api_base', 'dimension']:
        if key not in dense:
            errors.append(f'row3 OpenViking template missing embedding.dense.{key}')
    for key in ['provider', 'api_key', 'model', 'api_base']:
        if key not in row3_ov.get('vlm', {}):
            errors.append(f'row3 OpenViking template missing vlm.{key}')

    row4_ov = load_json(OPENVIKING_TEMPLATES / 'row4-compat-primary.local.json')
    if 'workspace' in row4_ov:
        errors.append('row4 OpenViking template must use storage.workspace, not workspace.root')
    if row4_ov.get('storage', {}).get('workspace') != 'storage/{run_id}/{group}/openviking-workspace':
        errors.append('row4 OpenViking template storage.workspace drifted')
    if row4_ov.get('server', {}).get('port') is None:
        errors.append('row4 OpenViking template missing server.port')
    if 'log' not in row4_ov:
        errors.append('row4 OpenViking template must materialize log settings')
    dense = row4_ov.get('embedding', {}).get('dense', {})
    for key in ['provider', 'api_key', 'model', 'api_base', 'dimension']:
        if key not in dense:
            errors.append(f'row4 OpenViking template missing embedding.dense.{key}')
    for key in ['provider', 'api_key', 'model', 'api_base']:
        if key not in row4_ov.get('vlm', {}):
            errors.append(f'row4 OpenViking template missing vlm.{key}')

    evidence = load_json(PUBLIC_EVIDENCE_MANIFEST)
    if 'row3' not in evidence or 'row4' not in evidence:
        errors.append('public evidence manifest must include row3 and row4 sections')


def validate_group_runtime(group: str, errors: list[str], notes: list[str]) -> None:
    apply_env_file()
    env_map = merged_env()
    spec = get_group_spec(group)
    mapping = {'run_id': 'preflight', 'group': group}

    versions = load_json(VERSIONS_MANIFEST)
    readiness = group_readiness(group, versions)
    if not readiness:
        errors.append(f'env/versions_manifest.json missing group_readiness for {group}')
    elif not readiness.get('ready_for_formal_wrapper'):
        errors.append(
            f'{group} is not ready per env/versions_manifest.json: ' + '; '.join(readiness.get('blocking_reasons') or ['unknown readiness failure'])
        )

    if env_map.get('OPENCLAW_BASE_URL') in (None, ''):
        errors.append('missing OPENCLAW_BASE_URL for formal gateway runs')
    if env_map.get('OPENCLAW_GATEWAY_TOKEN') in (None, ''):
        errors.append('missing OPENCLAW_GATEWAY_TOKEN for formal gateway runs')

    oc_template_path = OPENCLAW_TEMPLATES / f'{group}.json'
    ov_template_path = OPENVIKING_TEMPLATES / f'{group}.local.json'

    for path in [oc_template_path, ov_template_path]:
        if not path.exists():
            continue
        template = load_json(path)
        unresolved = missing_env_vars(template, env_map)
        if unresolved:
            errors.append(f'{rel(path)} missing env vars: {unresolved}')
        else:
            try:
                render_placeholders(template, mapping, expand_env=True, env=env_map, strict_env=True)
            except Exception as exc:
                errors.append(f'{rel(path)} could not be fully materialized: {exc}')

    for env_name in spec.get('required_actual_configs', []):
        raw_value = (env_map.get(env_name) or '').strip()
        path_value = Path(raw_value).expanduser() if raw_value else None
        if path_value is None or str(path_value).strip() == '.':
            errors.append(f'{group} runtime requires env var {env_name}')
            continue
        if not path_value.exists():
            errors.append(f'{group} runtime required config missing: {env_name} -> {path_value}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', default=None, help='Optionally validate env/materialization readiness for one group')
    args = parser.parse_args()

    errors: list[str] = []
    notes: list[str] = []

    validate_repo_structure(errors, notes)
    if not errors:
        validate_templates(errors, notes)
    if args.group and not errors:
        validate_group_runtime(args.group, errors, notes)

    print('Preflight notes:')
    for note in notes:
        print(f'  - {note}')
    if errors:
        print('Preflight errors:')
        for err in errors:
            print(f'  - {err}')
        raise SystemExit(1)
    print('Preflight passed.')


if __name__ == '__main__':
    main()
