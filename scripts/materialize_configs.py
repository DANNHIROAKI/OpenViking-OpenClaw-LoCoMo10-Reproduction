from __future__ import annotations

import argparse
from pathlib import Path

from _common import ROOT, apply_env_file, ensure_dir, load_json, render_placeholders, strip_repro_meta, write_json

OPENCLAW_TEMPLATES = ROOT / 'env/openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env/openviking_config_templates'



def materialize(group: str, run_id: str, out_dir: Path) -> dict[str, str]:
    env = apply_env_file()
    mapping = {'run_id': run_id, 'group': group}
    outputs: dict[str, str] = {}

    target_dir = ensure_dir(out_dir / run_id / group)
    oc_out = target_dir / 'openclaw.json'
    ov_out = target_dir / 'ov.conf'
    render_env = dict(env)
    render_env.setdefault('OPENCLAW_CONFIG_PATH', str(oc_out))
    render_env.setdefault('OPENVIKING_CONFIG_PATH', str(ov_out))

    ov_template_path = OPENVIKING_TEMPLATES / f'{group}.local.json'
    if ov_template_path.exists():
        ov_template = load_json(ov_template_path)
        ov_rendered = strip_repro_meta(
            render_placeholders(ov_template, mapping, expand_env=True, env=render_env, strict_env=True)
        )
        write_json(ov_out, ov_rendered)
        outputs['OPENVIKING_CONFIG_PATH'] = str(ov_out)

    oc_template_path = OPENCLAW_TEMPLATES / f'{group}.json'
    if oc_template_path.exists():
        oc_template = load_json(oc_template_path)
        oc_rendered = strip_repro_meta(
            render_placeholders(oc_template, mapping, expand_env=True, env=render_env, strict_env=True)
        )
        write_json(oc_out, oc_rendered)
        outputs['OPENCLAW_CONFIG_PATH'] = str(oc_out)

    return outputs



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('--out-dir', default='runtime_configs')
    args = parser.parse_args()
    outputs = materialize(args.group, args.run_id, Path(args.out_dir))
    if not outputs:
        raise SystemExit(f'no templates found for group {args.group}')
    for key, value in outputs.items():
        print(f'{key}={value}')


if __name__ == '__main__':
    main()
