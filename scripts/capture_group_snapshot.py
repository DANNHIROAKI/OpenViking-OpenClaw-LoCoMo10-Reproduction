from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from _common import (
    ROOT,
    collect_env_placeholders,
    ensure_dir,
    get_claim_decision,
    get_group_spec,
    load_json,
    merged_env,
    missing_env_vars,
    parse_json_text,
    path_label,
    redact_sensitive_tree,
    render_materialized_config,
    render_placeholders,
    run_shell,
    sha256_file,
    strip_repro_meta,
    subset_mismatches,
    utc_now,
    write_json,
)
from runtime_architecture import evaluate_runtime_architecture, normalize_runtime_architecture

OPENCLAW_TEMPLATES = ROOT / 'env/openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env/openviking_config_templates'
VERSIONS_MANIFEST = ROOT / 'env/versions_manifest.json'


def _load_json_loose(path: Path) -> tuple[Any | None, str | None]:
    try:
        return load_json(path), None
    except Exception as exc:
        return None, str(exc)


def _compare_template_to_actual(
    *,
    template_obj: dict[str, Any],
    actual_json: Any | None,
    actual_parse_error: str | None,
    mapping: dict[str, str],
    env: dict[str, str],
) -> dict[str, Any]:
    env_vars = sorted(collect_env_placeholders(template_obj))
    comparison: dict[str, Any] = {
        'required_env_vars': env_vars,
        'missing_env_vars': missing_env_vars(template_obj, env),
        'actual_json_parsed': actual_json is not None,
        'actual_json_parse_error': actual_parse_error,
        'structural_subset_match': None,
        'structural_mismatches': [],
        'exact_subset_match': None,
        'exact_mismatches': [],
    }

    if actual_json is None:
        if comparison['actual_json_parse_error'] is None:
            comparison['actual_json_parse_error'] = 'actual config file missing'
        return comparison

    rendered_structural = strip_repro_meta(render_placeholders(template_obj, mapping, expand_env=False, strict_env=False))
    structural_mismatches = subset_mismatches(rendered_structural, actual_json)
    comparison['structural_subset_match'] = len(structural_mismatches) == 0
    comparison['structural_mismatches'] = structural_mismatches[:50]

    if comparison['missing_env_vars']:
        return comparison

    rendered_exact = render_materialized_config(template_obj, mapping, env=env, strict_env=True)
    exact_mismatches = subset_mismatches(rendered_exact, actual_json)
    comparison['exact_subset_match'] = len(exact_mismatches) == 0
    comparison['exact_mismatches'] = exact_mismatches[:50]
    return comparison


def _private_snapshot_dir(run_id: str, group: str) -> Path:
    return ensure_dir(ROOT / 'storage' / run_id / group / 'private_snapshots')


def _capture_actual_snapshot(
    *,
    requested_path: str | None,
    public_dir: Path,
    private_dir: Path,
    public_stem: str,
    private_name_base: str,
) -> tuple[dict[str, Any], Path | None, Any | None, str | None]:
    info: dict[str, Any] = {}
    if not requested_path:
        return info, None, None, 'actual config path not provided'

    path = Path(requested_path).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    info['actual_snapshot_path_requested'] = str(path)
    if not path.exists():
        info['actual_snapshot_missing'] = True
        return info, path, None, 'actual config file missing'

    ensure_dir(public_dir)
    ensure_dir(private_dir)
    private_dest = private_dir / f'{private_name_base}.actual.raw{path.suffix or ".json"}'
    shutil.copy2(path, private_dest)

    raw_json, parse_error = _load_json_loose(path)
    public_dest = public_dir / f'{public_stem}.actual.redacted.json'
    if raw_json is None:
        write_json(
            public_dest,
            {
                '_capture_error': 'actual config could not be parsed as JSON; raw public snapshot omitted',
                'requested_path': str(path),
                'private_raw_snapshot': str(private_dest.relative_to(ROOT)),
            },
        )
        redacted_paths: list[str] = []
        redaction_applied = True
    else:
        redacted_json, redacted_paths = redact_sensitive_tree(raw_json)
        write_json(public_dest, redacted_json)
        redaction_applied = True

    info.update(
        {
            'actual_snapshot': str(public_dest.relative_to(ROOT)),
            'actual_snapshot_public': str(public_dest.relative_to(ROOT)),
            'actual_snapshot_private': str(private_dest.relative_to(ROOT)),
            'actual_sha256': sha256_file(public_dest),
            'actual_redacted_sha256': sha256_file(public_dest),
            'actual_unredacted_sha256': sha256_file(private_dest),
            'redaction_applied': redaction_applied,
            'redacted_paths': redacted_paths,
        }
    )
    return info, path, raw_json, parse_error


def _load_materialization_context(env: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest: dict[str, Any] = {}
    runtime_audit_freeze: dict[str, Any] = {}

    manifest_raw = env.get('REPRO_MATERIALIZATION_MANIFEST')
    if manifest_raw:
        manifest_path = Path(manifest_raw).expanduser()
        if not manifest_path.is_absolute():
            manifest_path = (ROOT / manifest_path).resolve()
        if manifest_path.exists():
            manifest = load_json(manifest_path)
            runtime_audit_freeze = manifest.get('runtime_audit_freeze') or {}
    return manifest, runtime_audit_freeze


def _load_versions_group_specific_runtime_freeze(group: str) -> dict[str, Any]:
    if not VERSIONS_MANIFEST.exists():
        return {}
    versions = load_json(VERSIONS_MANIFEST)
    return {group: ((versions.get('group_specific_runtime_freeze') or {}).get(group) or {})}


def capture_group_snapshot(group: str, run_id: str, run_root: Path) -> dict[str, Any]:
    env = merged_env()
    spec = get_group_spec(group)
    claim = get_claim_decision(group)
    mapping = {'run_id': run_id, 'group': group}

    oc_template_path = OPENCLAW_TEMPLATES / f'{group}.json'
    ov_template_path = OPENVIKING_TEMPLATES / f'{group}.local.json'

    oc_snapshot_dir = ensure_dir(ROOT / 'env/openclaw_config_snapshots' / run_id)
    ov_snapshot_dir = ensure_dir(ROOT / 'env/openviking_config_snapshots' / run_id)
    private_snapshot_dir = _private_snapshot_dir(run_id, group)
    materialization_manifest, runtime_audit_freeze = _load_materialization_context(env)

    summary: dict[str, Any] = {
        'group': group,
        'run_id': run_id,
        'captured_at': utc_now(),
        'claim_class': claim['effective_claim_class'],
        'materialization_manifest': env.get('REPRO_MATERIALIZATION_MANIFEST'),
        'runtime_isolation': materialization_manifest.get('runtime_isolation') or {},
        'runtime_audit_freeze': runtime_audit_freeze,
        'versions_group_specific_runtime_freeze': _load_versions_group_specific_runtime_freeze(group),
        'openclaw': {},
        'openviking': {},
        'plugin_inventory': {},
        'runtime_architecture': {},
    }

    oc_template = None
    if oc_template_path.exists():
        oc_template = load_json(oc_template_path)
        oc_expected_for_audit = render_placeholders(oc_template, mapping, expand_env=False, strict_env=False)
        expected_path = oc_snapshot_dir / f'{group}.expected.json'
        write_json(expected_path, oc_expected_for_audit)
        summary['openclaw']['expected_snapshot'] = str(expected_path.relative_to(ROOT))
        summary['openclaw']['expected_sha256'] = sha256_file(expected_path)

    ov_template = None
    if ov_template_path.exists():
        ov_template = load_json(ov_template_path)
        ov_expected_for_audit = render_placeholders(ov_template, mapping, expand_env=False, strict_env=False)
        expected_path = ov_snapshot_dir / f'{group}.expected.json'
        write_json(expected_path, ov_expected_for_audit)
        summary['openviking']['expected_snapshot'] = str(expected_path.relative_to(ROOT))
        summary['openviking']['expected_sha256'] = sha256_file(expected_path)

    oc_actual_info, oc_actual_path, oc_actual_json, oc_parse_error = _capture_actual_snapshot(
        requested_path=env.get('OPENCLAW_CONFIG_PATH'),
        public_dir=oc_snapshot_dir,
        private_dir=private_snapshot_dir,
        public_stem=group,
        private_name_base='openclaw',
    )
    summary['openclaw'].update(oc_actual_info)
    if oc_template is not None:
        summary['openclaw']['comparison'] = _compare_template_to_actual(
            template_obj=oc_template,
            actual_json=oc_actual_json,
            actual_parse_error=oc_parse_error,
            mapping=mapping,
            env=env,
        )
        compare_path = oc_snapshot_dir / f'{group}.compare.json'
        write_json(compare_path, summary['openclaw']['comparison'])
        summary['openclaw']['comparison_report'] = str(compare_path.relative_to(ROOT))

    ov_actual_info, ov_actual_path, ov_actual_json, ov_parse_error = _capture_actual_snapshot(
        requested_path=env.get('OPENVIKING_CONFIG_PATH'),
        public_dir=ov_snapshot_dir,
        private_dir=private_snapshot_dir,
        public_stem=group,
        private_name_base='openviking',
    )
    summary['openviking'].update(ov_actual_info)
    if ov_template is not None:
        summary['openviking']['comparison'] = _compare_template_to_actual(
            template_obj=ov_template,
            actual_json=ov_actual_json,
            actual_parse_error=ov_parse_error,
            mapping=mapping,
            env=env,
        )
        compare_path = ov_snapshot_dir / f'{group}.compare.json'
        write_json(compare_path, summary['openviking']['comparison'])
        summary['openviking']['comparison_report'] = str(compare_path.relative_to(ROOT))

    list_cmd = env.get('OPENCLAW_PLUGINS_LIST_CMD', 'openclaw plugins list --json')
    cp = run_shell(list_cmd, check=False, env=env)
    list_stdout = oc_snapshot_dir / f'{group}.plugins.list.stdout.txt'
    list_stderr = oc_snapshot_dir / f'{group}.plugins.list.stderr.txt'
    list_stdout.write_text(cp.stdout, encoding='utf-8')
    list_stderr.write_text(cp.stderr, encoding='utf-8')
    summary['plugin_inventory']['list_stdout'] = str(list_stdout.relative_to(ROOT))
    summary['plugin_inventory']['list_stderr'] = str(list_stderr.relative_to(ROOT))
    summary['plugin_inventory']['list_returncode'] = cp.returncode

    list_json = parse_json_text(cp.stdout)
    if list_json is not None:
        parsed_path = oc_snapshot_dir / f'{group}.plugins.list.parsed.json'
        write_json(parsed_path, list_json)
        summary['plugin_inventory']['list_parsed_json'] = str(parsed_path.relative_to(ROOT))

    inspect_template = env.get('OPENCLAW_PLUGIN_INSPECT_CMD_TEMPLATE', 'openclaw plugins inspect {plugin_id} --json')
    inspect_outputs = []
    inspect_stdout_map: dict[str, str] = {}
    for plugin_id in spec.get('inspect_plugins', []):
        cmd = inspect_template.format(plugin_id=plugin_id)
        icp = run_shell(cmd, check=False, env=env)
        out = oc_snapshot_dir / f'{group}.inspect.{plugin_id}.stdout.txt'
        err = oc_snapshot_dir / f'{group}.inspect.{plugin_id}.stderr.txt'
        out.write_text(icp.stdout, encoding='utf-8')
        err.write_text(icp.stderr, encoding='utf-8')
        inspect_stdout_map[plugin_id] = icp.stdout
        item = {
            'plugin_id': plugin_id,
            'stdout': str(out.relative_to(ROOT)),
            'stderr': str(err.relative_to(ROOT)),
            'returncode': icp.returncode,
        }
        parsed_json = parse_json_text(icp.stdout)
        if parsed_json is not None:
            parsed_path = oc_snapshot_dir / f'{group}.inspect.{plugin_id}.parsed.json'
            write_json(parsed_path, parsed_json)
            item['parsed_json'] = str(parsed_path.relative_to(ROOT))
        inspect_outputs.append(item)
    summary['plugin_inventory']['inspect_outputs'] = inspect_outputs

    actual_openclaw_config = oc_actual_json if isinstance(oc_actual_json, dict) else {}
    normalized = normalize_runtime_architecture(
        list_stdout_text=cp.stdout,
        inspect_stdout_map=inspect_stdout_map,
        actual_openclaw_config=actual_openclaw_config,
        spec=spec,
    )
    normalized_path = oc_snapshot_dir / f'{group}.plugins.normalized.json'
    write_json(normalized_path, normalized)
    summary['plugin_inventory']['normalized'] = normalized
    summary['plugin_inventory']['normalized_report'] = str(normalized_path.relative_to(ROOT))

    runtime_report = evaluate_runtime_architecture(spec, normalized)
    runtime_path = oc_snapshot_dir / f'{group}.runtime-architecture.json'
    write_json(runtime_path, runtime_report)
    summary['runtime_architecture'] = {
        **runtime_report,
        'report': str(runtime_path.relative_to(ROOT)),
    }

    out_path = run_root / 'config_snapshot.json'
    write_json(out_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('run_root')
    args = parser.parse_args()
    run_root = Path(args.run_root)
    ensure_dir(run_root)
    snapshot = capture_group_snapshot(args.group, args.run_id, run_root)
    print(path_label(run_root / 'config_snapshot.json'))
    if snapshot.get('runtime_architecture', {}).get('overall_passed') is not True:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
