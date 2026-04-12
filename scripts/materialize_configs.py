from __future__ import annotations

import argparse
import datetime as dt
import shutil
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
    render_placeholders,
    sha256_file,
    storage_root,
    to_shell_exports,
    utc_now,
    write_json,
    write_text,
)

OPENCLAW_TEMPLATES = ROOT / 'env/openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env/openviking_config_templates'



def _resolve_out_dir(out_dir: Path) -> Path:
    return out_dir.resolve() if out_dir.is_absolute() else (ROOT / out_dir).resolve()



def _unique_suffix() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')



def _resolve_runtime_path(value: str | None) -> str | None:
    if value in (None, ''):
        return None
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return str(path)



def _template_manifest_entry(path: Path) -> dict[str, Any]:
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha256_file(path)}



def _openviking_workspace_path(rendered_ov_config: dict[str, Any] | None) -> str | None:
    if not isinstance(rendered_ov_config, dict):
        return None
    storage = rendered_ov_config.get('storage') or {}
    workspace = storage.get('workspace')
    if workspace in (None, ''):
        return None
    return _resolve_runtime_path(str(workspace))



def _extract_template_audit_freeze(template_obj: dict[str, Any], mapping: dict[str, str], render_env: dict[str, str]) -> dict[str, Any]:
    repro_meta = template_obj.get('__repro_meta__') or {}
    audit_freeze = repro_meta.get('audit_freeze')
    if not isinstance(audit_freeze, dict):
        return {}
    rendered = render_placeholders(audit_freeze, mapping, expand_env=True, env=render_env, strict_env=True)
    if not isinstance(rendered, dict):
        raise SystemExit('__repro_meta__.audit_freeze must render to an object')
    return rendered



def _derive_runtime_exports(
    render_env: dict[str, str],
    *,
    group: str,
    run_id: str,
    runtime_dir: Path,
    oc_out: Path,
    ov_out: Path,
    exports_out: Path,
    manifest_out: Path,
    has_openviking: bool,
    rendered_ov_config: dict[str, Any] | None,
) -> tuple[dict[str, str], dict[str, str], str | None]:
    storage_dir = storage_root(run_id, group).resolve()
    openclaw_home = (storage_dir / 'openclaw-home').resolve()
    openclaw_state_dir = (storage_dir / 'openclaw-state').resolve()

    exports: dict[str, str] = {
        'REPRO_GROUP': group,
        'REPRO_RUN_ID': run_id,
        'REPRO_RUNTIME_ENV_FILE': str(exports_out.resolve()),
        'REPRO_MATERIALIZATION_DIR': str(runtime_dir.resolve()),
        'REPRO_MATERIALIZATION_MANIFEST': str(manifest_out.resolve()),
        'OPENCLAW_CONFIG_PATH': str(oc_out.resolve()),
        'OPENCLAW_HOME': str(openclaw_home),
        'OPENCLAW_STATE_DIR': str(openclaw_state_dir),
    }

    workspace_path = None
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
        log_path = _resolve_runtime_path(log_file)
        if log_path:
            exports['OPENVIKING_LOG_FILE'] = log_path
            ensure_dir(Path(log_path).parent)

        workspace_path = _openviking_workspace_path(rendered_ov_config)
        if workspace_path:
            exports['OPENVIKING_WORKSPACE_PATH'] = workspace_path
            ensure_dir(Path(workspace_path))

        for key in ['OPENVIKING_DIAGNOSTIC_ENDPOINT', 'OPENVIKING_DIAGNOSTIC_CMD']:
            value = (render_env.get(key) or '').strip()
            if value:
                exports[key] = value

    ensure_dir(openclaw_home)
    ensure_dir(openclaw_state_dir)
    isolation = {
        'openclaw_home': str(openclaw_home),
        'openclaw_state_dir': str(openclaw_state_dir),
    }
    return exports, isolation, workspace_path



def materialize(group: str, run_id: str, out_dir: Path, *, force: bool = False) -> dict[str, Any]:
    mapping = {'run_id': run_id, 'group': group}
    base_env = merged_env()
    out_dir = _resolve_out_dir(out_dir)
    ensure_dir(out_dir)

    target_dir = out_dir / run_id / group
    suffix = _unique_suffix()
    replaced_previous_dir: Path | None = None
    materialization_mode = 'fresh'
    if target_dir.exists():
        if not force:
            raise SystemExit(f'runtime config dir already exists: {path_label(target_dir)}')
        replaced_previous_dir = out_dir / '_replaced' / suffix / run_id / group
        ensure_dir(replaced_previous_dir.parent)
        shutil.move(str(target_dir), str(replaced_previous_dir))
        materialization_mode = 'force-replaced'

    tmp_dir = out_dir / '.tmp' / f'{suffix}-{run_id}-{group}'
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    ensure_dir(tmp_dir)

    oc_out = tmp_dir / 'openclaw.json'
    ov_out = tmp_dir / 'ov.conf'
    exports_out = tmp_dir / 'exports.env'
    manifest_out = tmp_dir / 'materialization_manifest.json'

    final_oc_out = target_dir / 'openclaw.json'
    final_ov_out = target_dir / 'ov.conf'
    final_exports_out = target_dir / 'exports.env'
    final_manifest_out = target_dir / 'materialization_manifest.json'

    render_env = dict(base_env)
    render_env['OPENCLAW_CONFIG_PATH'] = str(final_oc_out.resolve())
    render_env['OPENVIKING_CONFIG_PATH'] = str(final_ov_out.resolve())

    outputs: dict[str, Any] = {
        'group': group,
        'run_id': run_id,
        'out_dir': str(target_dir.resolve()),
        'templates': {},
        'outputs': {},
        'consumed_env_vars': [],
        'runtime_audit_freeze': {},
    }

    consumed_env_vars: set[str] = set()
    has_openviking = False
    rendered_ov_config: dict[str, Any] | None = None
    runtime_audit_freeze: dict[str, Any] = {}

    try:
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
                'path': path_label(final_ov_out),
                'sha256': sha256_file(ov_out),
            }

        oc_template_path = OPENCLAW_TEMPLATES / f'{group}.json'
        if oc_template_path.exists():
            outputs['templates']['openclaw'] = _template_manifest_entry(oc_template_path)
            oc_template = load_json(oc_template_path)
            consumed_env_vars.update(collect_env_placeholders(oc_template))
            rendered_oc = render_materialized_config(oc_template, mapping, env=render_env, strict_env=True)
            if not isinstance(rendered_oc, dict):
                raise SystemExit(f'{path_label(oc_template_path)} did not render to a JSON object')
            write_json(oc_out, rendered_oc)
            outputs['outputs']['openclaw_config'] = {
                'path': path_label(final_oc_out),
                'sha256': sha256_file(oc_out),
            }
            audit_freeze = _extract_template_audit_freeze(oc_template, mapping, render_env)
            if audit_freeze:
                runtime_audit_freeze[group] = audit_freeze

        if not outputs['outputs']:
            raise SystemExit(f'no templates found for group {group}')

        runtime_exports, runtime_isolation, workspace_path = _derive_runtime_exports(
            render_env,
            group=group,
            run_id=run_id,
            runtime_dir=target_dir,
            oc_out=final_oc_out,
            ov_out=final_ov_out,
            exports_out=final_exports_out,
            manifest_out=final_manifest_out,
            has_openviking=has_openviking,
            rendered_ov_config=rendered_ov_config,
        )
        write_text(exports_out, to_shell_exports(runtime_exports))

        outputs['outputs']['exports_env'] = {
            'path': path_label(final_exports_out),
            'sha256': sha256_file(exports_out),
        }
        outputs['consumed_env_vars'] = sorted(consumed_env_vars)
        outputs['materialized_exports'] = runtime_exports
        outputs['runtime_isolation'] = runtime_isolation
        outputs['runtime_audit_freeze'] = runtime_audit_freeze

        created_from_templates = [item['path'] for item in outputs['templates'].values()]
        manifest = {
            'group': group,
            'run_id': run_id,
            'generated_at': utc_now(),
            'runtime_dir': str(target_dir.resolve()),
            'runtime_env_file': str(final_exports_out.resolve()),
            'openviking_workspace_path': workspace_path,
            'created_from_templates': created_from_templates,
            'materialization_mode': materialization_mode,
            'replaced_previous_dir': str(replaced_previous_dir.resolve()) if replaced_previous_dir else None,
            'templates': outputs['templates'],
            'outputs': outputs['outputs'],
            'consumed_env_vars': sorted(consumed_env_vars),
            'materialized_exports': runtime_exports,
            'runtime_isolation': runtime_isolation,
            'runtime_audit_freeze': runtime_audit_freeze,
        }
        write_json(manifest_out, manifest)
        outputs['outputs']['materialization_manifest'] = {
            'path': path_label(final_manifest_out),
            'sha256': sha256_file(manifest_out),
        }

        ensure_dir(target_dir.parent)
        tmp_dir.replace(target_dir)
    except Exception:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        raise

    return outputs



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('--out-dir', default='runtime_configs')
    parser.add_argument('--force', action='store_true', help='Replace an existing runtime config dir after backing it up under _replaced/')
    parser.add_argument('--shell-export', action='store_true', help='Print shell export lines for the generated runtime env file')
    args = parser.parse_args()

    outputs = materialize(args.group, args.run_id, Path(args.out_dir), force=args.force)
    exports_path = Path(outputs['materialized_exports']['REPRO_RUNTIME_ENV_FILE'])
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
