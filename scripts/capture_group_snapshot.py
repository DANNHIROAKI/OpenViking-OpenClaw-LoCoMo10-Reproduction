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


def _load_json_loose(path: Path) -> tuple[Any | None, str | None]:
    try:
        return load_json(path), None
    except Exception as exc:
        return None, str(exc)


def _compare_template_to_actual(
    *,
    template_obj: dict[str, Any],
    actual_path: Path | None,
    mapping: dict[str, str],
    env: dict[str, str],
) -> dict[str, Any]:
    env_vars = sorted(collect_env_placeholders(template_obj))
    comparison: dict[str, Any] = {
        'required_env_vars': env_vars,
        'missing_env_vars': missing_env_vars(template_obj, env),
        'actual_json_parsed': False,
        'actual_json_parse_error': None,
        'structural_subset_match': None,
        'structural_mismatches': [],
        'exact_subset_match': None,
        'exact_mismatches': [],
    }

    if actual_path is None or not actual_path.exists():
        comparison['actual_json_parse_error'] = 'actual config file missing'
        return comparison

    actual_json, parse_error = _load_json_loose(actual_path)
    if parse_error:
        comparison['actual_json_parse_error'] = parse_error
        return comparison

    comparison['actual_json_parsed'] = True

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


def _maybe_copy_actual(src: str | None, dest_dir: Path, stem: str) -> tuple[dict[str, Any], Path | None]:
    info: dict[str, Any] = {}
    if not src:
        return info, None
    path = Path(src).expanduser()
    if not path.exists():
        info['actual_snapshot_missing'] = True
        info['actual_snapshot_path_requested'] = str(path)
        return info, path
    dest = dest_dir / f'{stem}.actual{path.suffix or ".snapshot"}'
    shutil.copy2(path, dest)
    info['actual_snapshot'] = str(dest.relative_to(ROOT))
    info['actual_sha256'] = sha256_file(dest)
    info['actual_snapshot_path_requested'] = str(path)
    return info, path


def capture_group_snapshot(group: str, run_id: str, run_root: Path) -> dict[str, Any]:
    env = merged_env()
    spec = get_group_spec(group)
    claim = get_claim_decision(group)
    mapping = {'run_id': run_id, 'group': group}

    oc_template_path = OPENCLAW_TEMPLATES / f'{group}.json'
    ov_template_path = OPENVIKING_TEMPLATES / f'{group}.local.json'

    oc_snapshot_dir = ensure_dir(ROOT / 'env/openclaw_config_snapshots' / run_id)
    ov_snapshot_dir = ensure_dir(ROOT / 'env/openviking_config_snapshots' / run_id)

    summary: dict[str, Any] = {
        'group': group,
        'run_id': run_id,
        'captured_at': utc_now(),
        'claim_class': claim['effective_claim_class'],
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

    oc_actual_info, oc_actual_path = _maybe_copy_actual(env.get('OPENCLAW_CONFIG_PATH'), oc_snapshot_dir, group)
    summary['openclaw'].update(oc_actual_info)
    if oc_template is not None:
        summary['openclaw']['comparison'] = _compare_template_to_actual(
            template_obj=oc_template,
            actual_path=oc_actual_path,
            mapping=mapping,
            env=env,
        )
        compare_path = oc_snapshot_dir / f'{group}.compare.json'
        write_json(compare_path, summary['openclaw']['comparison'])
        summary['openclaw']['comparison_report'] = str(compare_path.relative_to(ROOT))

    ov_actual_info, ov_actual_path = _maybe_copy_actual(env.get('OPENVIKING_CONFIG_PATH'), ov_snapshot_dir, group)
    summary['openviking'].update(ov_actual_info)
    if ov_template is not None:
        summary['openviking']['comparison'] = _compare_template_to_actual(
            template_obj=ov_template,
            actual_path=ov_actual_path,
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

    actual_openclaw_config = load_json(oc_actual_path) if oc_actual_path and oc_actual_path.exists() else {}
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
    result = capture_group_snapshot(args.group, args.run_id, run_root)
    print(path_label(run_root / 'config_snapshot.json'))
    if result.get('runtime_architecture', {}).get('overall_passed') is not True:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
