from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import requests

from _common import (
    BENCHMARK_MANIFEST_PATH,
    CLAIM_DECISIONS_PATH,
    GROUP_DEFS_PATH,
    OPENCLAW_EVAL_DIR,
    ROOT,
    collect_env_placeholders,
    get_group_spec,
    group_readiness,
    is_relative_to,
    load_json,
    merged_env,
    missing_env_vars,
    missing_env_vars,
    render_placeholders,
    run_shell,
    sha256_file,
    storage_root,
    utc_now,
    write_json,
)
from freeze_versions import MODEL_ROUTE_REQUIRED_FIELDS, ROW2_RUNTIME_FREEZE_ENV
from repo_contract import (
    CI_WORKFLOW,
    ENV_EXAMPLE,
    GITIGNORE_PATH,
    README_PATH,
    disallowed_env_example_vars,
    gitignore_missing_required_patterns,
    missing_env_example_vars,
    official_targets_uses_mutable_refs,
    public_snapshot_candidates,
    readme_mentions_min_ci,
    tracked_junk_files,
    workflow_missing_required_commands,
)
from runtime_architecture import evaluate_runtime_architecture, normalize_runtime_architecture

OPENCLAW_TEMPLATES = ROOT / 'env/openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env/openviking_config_templates'
PUBLIC_EVIDENCE_MANIFEST = ROOT / 'env/public_evidence_manifest.json'
SOURCE_REGISTRY = ROOT / 'env/source_snapshot_registry.json'
SOURCE_MANIFEST = ROOT / 'env/source_manifest.json'
VERSIONS_MANIFEST = ROOT / 'env/versions_manifest.json'
OFFICIAL_TARGETS = ROOT / 'official_targets.json'

ROW3_ALLOWED = {
    'mode', 'configPath', 'port', 'baseUrl', 'agentId', 'apiKey', 'targetUri', 'timeoutMs',
    'autoCapture', 'captureMode', 'captureMaxLength', 'autoRecall', 'recallLimit',
    'recallScoreThreshold', 'ingestReplyAssist', 'ingestReplyAssistMinSpeakerTurns',
    'ingestReplyAssistMinChars',
}
ROW3_REQUIRED = set(ROW3_ALLOWED) - {'baseUrl', 'apiKey'}
ROW4_ALLOWED = {
    'mode', 'configPath', 'port', 'baseUrl', 'agentId', 'apiKey', 'targetUri', 'timeoutMs',
    'autoCapture', 'captureMode', 'captureMaxLength', 'autoRecall', 'recallLimit',
    'recallScoreThreshold', 'recallMaxContentChars', 'recallPreferAbstract', 'recallTokenBudget',
    'commitTokenThreshold', 'bypassSessionPatterns', 'ingestReplyAssist',
    'ingestReplyAssistMinSpeakerTurns', 'ingestReplyAssistMinChars',
    'ingestReplyAssistIgnoreSessionPatterns', 'emitStandardDiagnostics', 'logFindRequests',
}
ROW4_REQUIRED = {
    'mode', 'configPath', 'port', 'agentId', 'targetUri', 'timeoutMs', 'autoCapture',
    'captureMode', 'captureMaxLength', 'autoRecall', 'recallLimit', 'recallScoreThreshold',
    'recallMaxContentChars', 'recallPreferAbstract', 'recallTokenBudget', 'commitTokenThreshold',
    'bypassSessionPatterns', 'ingestReplyAssist', 'ingestReplyAssistMinSpeakerTurns',
    'ingestReplyAssistMinChars', 'emitStandardDiagnostics', 'logFindRequests',
}
SENSITIVE_KEY_RE = re.compile(r'(?i)(apikey|api_key|token|secret|password)')



def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)



def _resolve_env_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path



def _snapshot_has_unredacted_sensitive_value(path: Path) -> bool:
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        return False
    for line in text.splitlines():
        if '[REDACTED]' in line:
            continue
        if SENSITIVE_KEY_RE.search(line):
            return True
    return False



def get_plugin_entry(template: dict[str, Any], plugin_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
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
        SOURCE_REGISTRY,
        SOURCE_MANIFEST,
        VERSIONS_MANIFEST,
        OFFICIAL_TARGETS,
        PUBLIC_EVIDENCE_MANIFEST,
        ENV_EXAMPLE,
        GITIGNORE_PATH,
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

    registry = load_json(SOURCE_REGISTRY)
    manifest = load_json(SOURCE_MANIFEST)
    if 'generated_at' in manifest:
        errors.append('env/source_manifest.json should not contain volatile generated_at')
    registry_ids = {item['snapshot_id'] for item in registry.get('snapshots', [])}
    manifest_ids = {item['snapshot_id'] for item in manifest.get('snapshots', [])}
    if registry_ids != manifest_ids:
        errors.append('source manifest snapshot ids differ from source registry')
    for snap in manifest.get('snapshots', []):
        if 'fetched_at' in snap:
            errors.append(f"source manifest snapshot {snap.get('snapshot_id')} still uses fetched_at")
        if 'vendored_at' not in snap:
            errors.append(f"source manifest snapshot {snap.get('snapshot_id')} missing vendored_at")
        for file_item in snap.get('files', []):
            path = ROOT / file_item['path']
            if not path.exists():
                errors.append(f"source manifest file missing: {file_item['path']}")
                continue
            if sha256_file(path) != file_item['sha256']:
                errors.append(f"sha256 mismatch: {file_item['path']}")

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
    if 'parallel' not in eval_py:
        notes.append('Could not positively verify parallel handling in vendored eval.py; inspect manually.')

    if defs['tail_literal'] != "[remember what's said, keep existing memory]":
        errors.append('tail literal drifted from frozen spec')
    if defs['parallel'] != 1:
        errors.append('parallel drifted from frozen spec')

    evidence = load_json(PUBLIC_EVIDENCE_MANIFEST)
    items = evidence.get('evidence_items')
    if not isinstance(items, list) or not items:
        errors.append('public evidence manifest must contain a non-empty evidence_items list')
    else:
        for item in items:
            vendored = ROOT / item['vendored_local_path']
            if not vendored.exists():
                errors.append(f"public evidence file missing: {item['vendored_local_path']}")
                continue
            if sha256_file(vendored) != item['sha256']:
                errors.append(f"public evidence sha mismatch: {item['vendored_local_path']}")
            if '/blob/main/' in (item.get('blob_url') or ''):
                errors.append(f"public evidence blob_url must be immutable, not main: {item['blob_url']}")
    group_claims = evidence.get('group_claims') or {}
    for group in ['row3-openviking-minus-core', 'row4-compat-primary']:
        if group not in group_claims:
            errors.append(f'public evidence manifest missing group_claims entry for {group}')



def validate_versions_route_freeze_contract(errors: list[str], notes: list[str]) -> None:
    if not VERSIONS_MANIFEST.exists():
        errors.append('missing env/versions_manifest.json')
        return

    versions = load_json(VERSIONS_MANIFEST)
    if versions.get('capture_status') != 'captured':
        notes.append('env/versions_manifest.json is not captured yet; run python3 scripts/freeze_versions.py on the formal host before any official run')

    resolved = versions.get('resolved_model_freeze') or {}
    if resolved.get('required_fields') != MODEL_ROUTE_REQUIRED_FIELDS:
        errors.append('env/versions_manifest.json resolved_model_freeze.required_fields drifted from frozen schema')

    for required_group in ['row1-memory-core', 'row2-memory-lancedb', 'row3-openviking-minus-core', 'row4-compat-primary']:
        if required_group not in (versions.get('group_readiness') or {}):
            errors.append(f'env/versions_manifest.json missing group_readiness for {required_group}')

    judge_files = versions.get('judge_freeze', {}).get('snapshot_files', {})
    for name in ['judge.py', 'judge_util.py']:
        item = judge_files.get(name, {})
        if item and not item.get('sha256'):
            errors.append(f'judge freeze missing sha256 for {name}')

    row2_block = (versions.get('group_specific_runtime_freeze') or {}).get('row2-memory-lancedb') or {}
    if versions.get('capture_status') == 'captured':
        missing = [field for field in ROW2_RUNTIME_FREEZE_ENV if not row2_block.get(field)]
        if missing:
            errors.append('captured versions manifest missing row2 group_specific_runtime_freeze fields: ' + ', '.join(missing))
    else:
        required_fields = [field for field in ROW2_RUNTIME_FREEZE_ENV]
        if row2_block.get('required_fields') != required_fields:
            errors.append('pending versions manifest row2 required_fields drifted from frozen schema')



def validate_env_example_contract(errors: list[str], notes: list[str]) -> None:
    if not ENV_EXAMPLE.exists():
        errors.append('missing .env.example')
        return

    missing = missing_env_example_vars()
    if missing:
        errors.append(f'.env.example is missing required keys: {missing}')

    disallowed = disallowed_env_example_vars()
    if disallowed:
        errors.append(f'.env.example must not contain runtime-generated keys: {disallowed}')



def validate_ci_contract(errors: list[str], notes: list[str]) -> None:
    mentions_ci = readme_mentions_min_ci()
    if mentions_ci and not CI_WORKFLOW.exists():
        errors.append('README declares a minimal CI workflow, but .github/workflows/ci.yml is missing')
        return
    if not CI_WORKFLOW.exists():
        notes.append('minimal CI workflow is absent')
        return

    missing_cmds = workflow_missing_required_commands()
    if missing_cmds:
        errors.append(f'ci workflow is missing required commands: {missing_cmds}')

    if mentions_ci and not README_PATH.exists():
        errors.append('README is missing while CI contract expects it')



def validate_gitignore_contract(errors: list[str], notes: list[str]) -> None:
    if not GITIGNORE_PATH.exists():
        errors.append('missing .gitignore')
        return
    missing = gitignore_missing_required_patterns()
    if missing:
        errors.append(f'.gitignore is missing required patterns: {missing}')



def validate_official_targets_immutable_refs(errors: list[str], notes: list[str]) -> None:
    mutable = official_targets_uses_mutable_refs()
    if mutable:
        errors.append(f'official_targets.json still references mutable refs: {mutable}')



def validate_no_junk_files(errors: list[str], notes: list[str]) -> None:
    junk = tracked_junk_files()
    if junk:
        errors.append(f'remove tracked junk files/directories: {junk}')



def validate_public_snapshot_contract(errors: list[str], notes: list[str]) -> None:
    offenders: list[str] = []
    for path in public_snapshot_candidates():
        lowered = path.name.lower()
        rel_path = rel(path)
        if '.raw.' in lowered:
            offenders.append(rel_path)
            continue
        if '.actual' not in lowered:
            continue
        if _snapshot_has_unredacted_sensitive_value(path):
            offenders.append(rel_path)
    if offenders:
        errors.append('public config snapshot directory contains raw or unredacted actual snapshots: ' + ', '.join(offenders))



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
    row2_meta = row2.get('__repro_meta__') or {}
    audit_freeze = row2_meta.get('audit_freeze') or {}
    if audit_freeze.get('lancedb_embedding_provider') != '${LANCEDB_EMBEDDING_PROVIDER}':
        errors.append('row2 template __repro_meta__.audit_freeze.lancedb_embedding_provider drifted')

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



def _run_runtime_architecture_online(group: str, env_map: dict[str, str]) -> dict[str, Any]:
    spec = get_group_spec(group)
    openclaw_path = Path(env_map['OPENCLAW_CONFIG_PATH']).expanduser()
    actual_openclaw = load_json(openclaw_path)

    list_cmd = env_map.get('OPENCLAW_PLUGINS_LIST_CMD', 'openclaw plugins list --json')
    list_cp = run_shell(list_cmd, check=False, env=env_map)
    inspect_template = env_map.get('OPENCLAW_PLUGIN_INSPECT_CMD_TEMPLATE', 'openclaw plugins inspect {plugin_id} --json')
    inspect_stdout_map: dict[str, str] = {}
    for plugin_id in spec.get('inspect_plugins', []):
        cp = run_shell(inspect_template.format(plugin_id=plugin_id), check=False, env=env_map)
        inspect_stdout_map[plugin_id] = cp.stdout

    normalized = normalize_runtime_architecture(
        list_stdout_text=list_cp.stdout,
        inspect_stdout_map=inspect_stdout_map,
        actual_openclaw_config=actual_openclaw,
        spec=spec,
    )
    runtime_report = evaluate_runtime_architecture(spec, normalized)
    return {
        'list_returncode': list_cp.returncode,
        'normalized': normalized,
        'runtime_report': runtime_report,
    }



def validate_group_runtime(group: str, run_id: str, online: bool, errors: list[str], notes: list[str]) -> Path:
    env_map = merged_env()
    spec = get_group_spec(group)
    mapping = {'run_id': run_id, 'group': group}
    report: dict[str, Any] = {
        'group': group,
        'run_id': run_id,
        'generated_at': utc_now(),
        'online': online,
        'materialization_ok': False,
        'actual_config_paths_exist': False,
        'runtime_architecture_ok': None,
        'openviking_health_ok': None,
        'blocking_reasons': [],
        'notes': [],
    }

    versions = load_json(VERSIONS_MANIFEST)
    readiness = group_readiness(group, versions)
    if not readiness:
        report['blocking_reasons'].append(f'env/versions_manifest.json missing group_readiness for {group}')
    elif versions.get('capture_status') != 'captured':
        report['blocking_reasons'].append('env/versions_manifest.json is not captured; run python3 scripts/freeze_versions.py on the formal experiment host')
    elif not readiness.get('ready_for_formal_wrapper'):
        report['blocking_reasons'].append(
            f'{group} is not ready per env/versions_manifest.json: ' + '; '.join(readiness.get('blocking_reasons') or ['unknown readiness failure'])
        )

    if env_map.get('OPENCLAW_BASE_URL') in (None, ''):
        report['blocking_reasons'].append('missing OPENCLAW_BASE_URL for formal gateway runs')
    if env_map.get('OPENCLAW_GATEWAY_TOKEN') in (None, ''):
        report['blocking_reasons'].append('missing OPENCLAW_GATEWAY_TOKEN for formal gateway runs')

    oc_template_path = OPENCLAW_TEMPLATES / f'{group}.json'
    ov_template_path = OPENVIKING_TEMPLATES / f'{group}.local.json'
    materialization_errors = []
    for path in [oc_template_path, ov_template_path]:
        if not path.exists():
            continue
        template = load_json(path)
        unresolved = missing_env_vars(template, env_map)
        if unresolved:
            materialization_errors.append(f'{rel(path)} missing env vars: {unresolved}')
        else:
            try:
                render_placeholders(template, mapping, expand_env=True, env=env_map, strict_env=True)
            except Exception as exc:
                materialization_errors.append(f'{rel(path)} could not be fully materialized: {exc}')
    if materialization_errors:
        report['blocking_reasons'].extend(materialization_errors)
    else:
        report['materialization_ok'] = True

    runtime_env_path = _resolve_env_path(env_map.get('REPRO_RUNTIME_ENV_FILE'))
    manifest_path = _resolve_env_path(env_map.get('REPRO_MATERIALIZATION_MANIFEST'))
    runtime_dir = _resolve_env_path(env_map.get('REPRO_MATERIALIZATION_DIR'))
    if runtime_env_path is None or not runtime_env_path.exists():
        report['blocking_reasons'].append('missing bound REPRO_RUNTIME_ENV_FILE; run materialize first')
    if manifest_path is None or not manifest_path.exists():
        report['blocking_reasons'].append('missing bound REPRO_MATERIALIZATION_MANIFEST; run materialize first')
    if runtime_dir is None or not runtime_dir.exists():
        report['blocking_reasons'].append('missing bound REPRO_MATERIALIZATION_DIR; run materialize first')

    manifest_obj = None
    if manifest_path is not None and manifest_path.exists():
        manifest_obj = load_json(manifest_path)
        if manifest_obj.get('group') != group:
            report['blocking_reasons'].append('materialization manifest group mismatch')
        if manifest_obj.get('run_id') != run_id:
            report['blocking_reasons'].append('materialization manifest run_id mismatch')

    required_paths = {}
    path_errors = []
    for env_name in spec.get('required_actual_configs', []):
        raw_value = (env_map.get(env_name) or '').strip()
        path_value = Path(raw_value).expanduser() if raw_value else None
        if path_value is None or not raw_value:
            path_errors.append(f'{group} runtime requires env var {env_name}')
            continue
        if not path_value.exists():
            path_errors.append(f'{group} runtime required config missing: {env_name} -> {path_value}')
            continue
        required_paths[env_name] = path_value.resolve()
    if path_errors:
        report['blocking_reasons'].extend(path_errors)
    else:
        report['actual_config_paths_exist'] = True
        report['actual_config_paths'] = {key: str(value) for key, value in required_paths.items()}

    if runtime_dir is not None and runtime_dir.exists():
        expected_runtime_dir = runtime_dir.resolve()
        if expected_runtime_dir.name != group or expected_runtime_dir.parent.name != run_id:
            report['blocking_reasons'].append('bound runtime materialization dir does not match requested run_id/group')
        for env_name in ['OPENCLAW_CONFIG_PATH', 'OPENVIKING_CONFIG_PATH']:
            raw = env_map.get(env_name)
            if not raw:
                continue
            path = _resolve_env_path(raw)
            if path is None or not path.exists():
                continue
            if not is_relative_to(path, expected_runtime_dir):
                report['blocking_reasons'].append(f'{env_name} is not located under the bound runtime materialization dir')

    expected_storage_root = storage_root(run_id, group).resolve()
    for env_name in ['OPENCLAW_HOME', 'OPENCLAW_STATE_DIR']:
        raw = env_map.get(env_name)
        if not raw:
            report['blocking_reasons'].append(f'missing {env_name} in runtime exports')
            continue
        path = _resolve_env_path(raw)
        if path is None:
            report['blocking_reasons'].append(f'invalid {env_name} path')
            continue
        if not path.exists():
            report['blocking_reasons'].append(f'{env_name} path does not exist: {path}')
            continue
        if not is_relative_to(path, expected_storage_root):
            report['blocking_reasons'].append(f'{env_name} escaped storage/{run_id}/{group}')

    if online and report['actual_config_paths_exist']:
        try:
            runtime_online = _run_runtime_architecture_online(group, env_map)
            runtime_report = runtime_online['runtime_report']
            report['runtime_architecture_ok'] = runtime_report.get('overall_passed') is True
            report['runtime_architecture'] = {
                'list_returncode': runtime_online['list_returncode'],
                'runtime_report': runtime_report,
            }
            if runtime_report.get('overall_passed') is not True:
                report['blocking_reasons'].extend(runtime_report.get('blocking_reasons', []))
        except Exception as exc:
            report['runtime_architecture_ok'] = False
            report['blocking_reasons'].append(f'online runtime architecture check failed: {exc}')

        if spec.get('require_openviking_health'):
            health_url = env_map.get('OPENVIKING_HEALTH_URL')
            if not health_url:
                report['openviking_health_ok'] = False
                report['blocking_reasons'].append('OPENVIKING_HEALTH_URL missing for online preflight')
            else:
                try:
                    resp = requests.get(health_url, timeout=10)
                    report['openviking_health_ok'] = 200 <= resp.status_code < 300
                    report['openviking_health'] = {'url': health_url, 'status_code': resp.status_code, 'body': resp.text[:1000]}
                    if report['openviking_health_ok'] is not True:
                        report['blocking_reasons'].append(f'OpenViking health endpoint returned {resp.status_code}')
                except Exception as exc:
                    report['openviking_health_ok'] = False
                    report['blocking_reasons'].append(f'OpenViking health check failed: {exc}')

    report_path = ROOT / 'reports' / 'preflight' / group / f'{run_id}.json'
    write_json(report_path, report)
    if report['blocking_reasons']:
        errors.extend(report['blocking_reasons'])
    return report_path



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', default=None, help='Optionally validate env/materialization readiness for one group')
    parser.add_argument('--run-id', default='preflight')
    parser.add_argument('--online', action='store_true', help='Run runtime architecture and health checks against the live installation')
    args = parser.parse_args()

    errors: list[str] = []
    notes: list[str] = []
    report_path: Path | None = None

    validate_repo_structure(errors, notes)
    if not errors:
        validate_versions_route_freeze_contract(errors, notes)
    if not errors:
        validate_env_example_contract(errors, notes)
    if not errors:
        validate_ci_contract(errors, notes)
    if not errors:
        validate_gitignore_contract(errors, notes)
    if not errors:
        validate_official_targets_immutable_refs(errors, notes)
    if not errors:
        validate_no_junk_files(errors, notes)
    if not errors:
        validate_public_snapshot_contract(errors, notes)
    if not errors:
        validate_templates(errors, notes)
    if args.group and not errors:
        report_path = validate_group_runtime(args.group, args.run_id, args.online, errors, notes)

    print('Preflight notes:')
    for note in notes:
        print(f'  - {note}')
    if report_path is not None:
        print(f'Preflight report: {rel(report_path)}')
    if errors:
        print('Preflight errors:')
        for err in errors:
            print(f'  - {err}')
        raise SystemExit(1)
    print('Preflight passed.')


if __name__ == '__main__':
    main()
