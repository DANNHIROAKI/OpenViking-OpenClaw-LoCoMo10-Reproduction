from __future__ import annotations

from pathlib import Path
from typing import Iterable

from _common import ROOT, collect_env_placeholders, load_env_file, load_json

README_PATH = ROOT / 'README.md'
CI_WORKFLOW = ROOT / '.github' / 'workflows' / 'ci.yml'
ENV_EXAMPLE = ROOT / '.env.example'
OPENCLAW_TEMPLATES = ROOT / 'env' / 'openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env' / 'openviking_config_templates'

RUNTIME_GENERATED_ENV_VARS = {
    'OPENCLAW_CONFIG_PATH',
    'OPENVIKING_CONFIG_PATH',
    'REPRO_RUNTIME_ENV_FILE',
    'REPRO_MATERIALIZATION_DIR',
    'REPRO_MATERIALIZATION_MANIFEST',
    'OPENVIKING_WORKSPACE_PATH',
    'REPRO_GROUP',
    'REPRO_RUN_ID',
}

SCRIPT_REQUIRED_USER_ENV_VARS = {
    'OPENCLAW_BASE_URL',
    'OPENCLAW_GATEWAY_TOKEN',
    'OPENCLAW_MODEL_PROVIDER',
    'OPENCLAW_MODEL_API_BASE',
    'OPENCLAW_MODEL_DEPLOYMENT_ID',
    'OPENCLAW_MODEL_ID',
    'JUDGE_MODEL',
}

REQUIRED_CI_COMMAND_SNIPPETS = [
    'pytest -q',
    'python scripts/build_benchmark.py',
    'python scripts/generate_source_manifest.py',
    'python scripts/preflight.py',
]

README_MIN_CI_PHRASE = '仓库附带最小 CI'


def _template_paths() -> list[Path]:
    return sorted(OPENCLAW_TEMPLATES.glob('*.json')) + sorted(OPENVIKING_TEMPLATES.glob('*.json'))



def template_required_env_vars() -> set[str]:
    required: set[str] = set()
    for path in _template_paths():
        required.update(collect_env_placeholders(load_json(path)))
    return required - RUNTIME_GENERATED_ENV_VARS



def required_env_example_vars() -> set[str]:
    return template_required_env_vars() | SCRIPT_REQUIRED_USER_ENV_VARS



def load_env_example_keys(path: Path | None = None) -> set[str]:
    return set(load_env_file(path or ENV_EXAMPLE).keys())



def missing_env_example_vars(path: Path | None = None) -> list[str]:
    present = load_env_example_keys(path)
    return sorted(required_env_example_vars() - present)



def disallowed_env_example_vars(path: Path | None = None) -> list[str]:
    present = load_env_example_keys(path)
    return sorted(present & RUNTIME_GENERATED_ENV_VARS)



def workflow_text(path: Path | None = None) -> str:
    workflow = path or CI_WORKFLOW
    if not workflow.exists():
        return ''
    return workflow.read_text(encoding='utf-8')



def workflow_missing_required_commands(path: Path | None = None) -> list[str]:
    text = workflow_text(path)
    return [snippet for snippet in REQUIRED_CI_COMMAND_SNIPPETS if snippet not in text]



def readme_text(path: Path | None = None) -> str:
    target = path or README_PATH
    if not target.exists():
        return ''
    return target.read_text(encoding='utf-8')



def readme_mentions_min_ci(path: Path | None = None) -> bool:
    return README_MIN_CI_PHRASE in readme_text(path)



def iter_required_template_vars() -> Iterable[str]:
    return iter(sorted(template_required_env_vars()))
