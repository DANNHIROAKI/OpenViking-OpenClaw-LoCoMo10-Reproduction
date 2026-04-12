from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _common import (
    ROOT,
    collect_env_placeholders,
    ensure_dir,
    load_json,
    merged_env,
    path_label,
    render_materialized_config,
    sha256_file,
    to_shell_exports,
    utc_now,
    write_json,
    write_text,
)

OPENCLAW_TEMPLATES = ROOT / 'env/openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env/openviking_config_templates'


def _derive_runtime_exports(
    render_env: dict[str, str],
    *,
    group: str,
    run_id: str,
    oc_out: Path,
    ov_out: Path,
    has_openviking: bool,
    rendered_ov_config: dict[str, Any] | None,
) -> dict[str, str]:
    exports: dict[str, str] = {
        'REPRO_GROUP': group,
        'REPRO_RUN_ID': run_id,
        'OPENCLAW_CONFIG_PATH': str(oc_out.resolve()),
    }
    if has_openviking:
        exports['OPENVIKING_CONFIG_PATH'] = str(ov_out.resolve())
        host = render_env.get('OPENVIKING_SERVER_HOST') or str((rendered_ov_config or {}).get('server', {}).get('host') or '127.0.0.1')
        port = render_env.get('OPENVIKING_SERVER_PORT') or str((rendered_ov_config or {}).get('server', {}).get('port') or '')
        health_url = render_env.get('OPENVIKING_HEALTH_URL')
        if not health_url and port:
            health_url = f'http://{host}:{port}/health'
        if health_url:
            exports['OPENVIKING_HEALTH_URL'] = health_url
        log_file = render_env.get('OPENVIKING_LOG_FILE')
        if not log_file and isinstance(rendered_ov_config, dict):
            log_file = str((rendered_ov_config.get('log') or {}).get('output') or '').strip() or None
        if log_file:
            exports['OPENVIKING_LOG_FILE'] = log_file
    return exports


def _template_manifest_entry(path: Path) -> dict[str, Any]:
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha256_file(path)}


def materialize(group: str, run_id: str, out_dir: Path) -> dict[str, Any]:
    mapping = {'run_id': run_id, 'group': group}
    base_env = merged_env()

    target_dir = ensure_dir(out_dir / run_id / group)
    oc_out = target_dir / 'openclaw.json'
    ov_out = target_dir / 'ov.conf'
    exports_out = target_dir / 'exports.env'
    manifest_out = target_dir / 'materialization_manifest.json'

    render_env = dict(base_env)
    render_env['OPENCLAW_CONFIG_PATH'] = str(oc_out.resolve())
    render_env['OPENVIKING_CONFIG_PATH'] = str(ov_out.resolve())

    outputs: dict[str, Any] = {
        'group': group,
        'run_id': run_id,
        'out_dir': str(target_dir.resolve()),
        'templates': {},
        'outputs': {},
        'consumed_env_vars': [],
    }

    consumed_env_vars: set[str] = set()
    has_openviking = False
    rendered_ov_config: dict[str, Any] | None = None

    ov_template_path = OPENVIKING_TEMPLATES / f'{group}.local.json'
    if ov_template_path.exists():
        has_openviking = True
        outputs['templates']['openviking'] = _template_manifest_entry(ov_template_path)
        ov_template = load_json(ov_template_path)
        consumed_env_vars.update(collect_env_placeholders(ov_template))
        rendered_ov = render_materialized_config(ov_template, mapping, env=render_env, strict_env=True)
        if not isinstance(rendered_ov, dict):
            raise SystemExit(f'{path_label(ov_template_path)} did not render to a JSON object')
        rendered_ov_config = rendered_ov
        write_json(ov_out, rendered_ov_config)
        outputs['outputs']['openviking_config'] = {
            'path': path_label(ov_out),
            'sha256': sha256_file(ov_out),
        }

    oc_template_path = OPENCLAW_TEMPLATES / f'{group}.json'
    if oc_template_path.exists():
        outputs['templates']['openclaw'] = _template_manifest_entry(oc_template_path)
        oc_template = load_json(oc_template_path)
        consumed_env_vars.update(collect_env_placeholders(oc_template))
        rendered_oc = render_materialized_config(oc_template, mapping, env=render_env, strict_env=True)
        write_json(oc_out, rendered_oc)
        outputs['outputs']['openclaw_config'] = {
            'path': path_label(oc_out),
            'sha256': sha256_file(oc_out),
        }

    if not outputs['outputs']:
        raise SystemExit(f'no templates found for group {group}')

    runtime_exports = _derive_runtime_exports(
        render_env,
        group=group,
        run_id=run_id,
        oc_out=oc_out,
        ov_out=ov_out,
        has_openviking=has_openviking,
        rendered_ov_config=rendered_ov_config,
    )
    write_text(exports_out, to_shell_exports(runtime_exports))

    outputs['outputs']['exports_env'] = {
        'path': path_label(exports_out),
        'sha256': sha256_file(exports_out),
    }
    outputs['consumed_env_vars'] = sorted(consumed_env_vars)
    outputs['materialized_exports'] = runtime_exports

    manifest = {
        'group': group,
        'run_id': run_id,
        'generated_at': utc_now(),
        'templates': outputs['templates'],
        'outputs': outputs['outputs'],
        'consumed_env_vars': sorted(consumed_env_vars),
        'materialized_exports': runtime_exports,
    }
    write_json(manifest_out, manifest)
    outputs['outputs']['materialization_manifest'] = {
        'path': path_label(manifest_out),
        'sha256': sha256_file(manifest_out),
    }
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('--out-dir', default='runtime_configs')
    parser.add_argument('--shell-export', action='store_true', help='Print shell export lines for the generated runtime env file')
    args = parser.parse_args()

    outputs = materialize(args.group, args.run_id, Path(args.out_dir))
    exports_path = ROOT / outputs['outputs']['exports_env']['path']
    if args.shell_export:
        print(exports_path.read_text(encoding='utf-8'), end='')
        return

    print(
        '{\n'
        f'  "group": "{args.group}",\n'
        f'  "run_id": "{args.run_id}",\n'
        f'  "runtime_dir": "{path_label(Path(outputs["out_dir"]))}",\n'
        f'  "exports_env": "{outputs["outputs"]["exports_env"]["path"]}",\n'
        f'  "REPRO_MATERIALIZATION_MANIFEST": "{outputs["outputs"]["materialization_manifest"]["path"]}"\n'
        '}'
    )


if __name__ == '__main__':
    main()
