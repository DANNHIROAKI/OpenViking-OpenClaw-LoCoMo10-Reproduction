from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from _common import ROOT, collect_env_placeholders, load_env_file, load_json

README_PATH = ROOT / 'README.md'
CI_WORKFLOW = ROOT / '.github' / 'workflows' / 'ci.yml'
ENV_EXAMPLE = ROOT / '.env.example'
GITIGNORE_PATH = ROOT / '.gitignore'
OFFICIAL_TARGETS_PATH = ROOT / 'official_targets.json'
OPENCLAW_TEMPLATES = ROOT / 'env' / 'openclaw_config_templates'
OPENVIKING_TEMPLATES = ROOT / 'env' / 'openviking_config_templates'
PUBLIC_OPENCLAW_SNAPSHOTS = ROOT / 'env' / 'openclaw_config_snapshots'
PUBLIC_OPENVIKING_SNAPSHOTS = ROOT / 'env' / 'openviking_config_snapshots'

RUNTIME_GENERATED_ENV_VARS = {
    'OPENCLAW_CONFIG_PATH',
    'OPENCLAW_HOME',
    'OPENCLAW_STATE_DIR',
    'OPENVIKING_CONFIG_PATH',
    'OPENVIKING_HEALTH_URL',
    'OPENVIKING_LOG_FILE',
    'OPENVIKING_WORKSPACE_PATH',
    'REPRO_GROUP',
    'REPRO_RUN_ID',
    'REPRO_RUNTIME_ENV_FILE',
    'REPRO_MATERIALIZATION_DIR',
    'REPRO_MATERIALIZATION_MANIFEST',
}

SCRIPT_REQUIRED_USER_ENV_VARS = {
    'OPENCLAW_BASE_URL',
    'OPENCLAW_GATEWAY_TOKEN',
    'OPENCLAW_MODEL_PROVIDER',
    'OPENCLAW_MODEL_API_BASE',
    'OPENCLAW_MODEL_DEPLOYMENT_ID',
    'OPENCLAW_MODEL_ID',
    'OPENCLAW_MODEL_TEMPERATURE',
    'OPENCLAW_MODEL_MAX_TOKENS',
    'OPENCLAW_MODEL_REASONING',
    'JUDGE_MODEL',
}

REQUIRED_CI_COMMAND_SNIPPETS = [
    'pytest -q',
    'python scripts/build_benchmark.py',
    'python scripts/generate_source_manifest.py',
    'python scripts/preflight.py',
]

README_MIN_CI_PHRASE = '仓库附带最小 CI'
REQUIRED_GITIGNORE_PATTERNS = [
    '.env',
    '.venv/',
    '__pycache__/',
    '.pytest_cache/',
    '.DS_Store',
    'runtime_configs/',
    'reports/preflight/',
    'storage/*',
    '!storage/.gitkeep',
    'storage/**/private_snapshots/',
    'scripts/__pycache__/',
    'tests/__pycache__/',
]

JUNK_FILE_NAMES = {'.DS_Store'}
JUNK_DIR_NAMES = {'__pycache__'}


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



def gitignore_text(path: Path | None = None) -> str:
    target = path or GITIGNORE_PATH
    if not target.exists():
        return ''
    return target.read_text(encoding='utf-8')



def required_gitignore_patterns() -> list[str]:
    return list(REQUIRED_GITIGNORE_PATTERNS)



def gitignore_missing_required_patterns(path: Path | None = None) -> list[str]:
    text = gitignore_text(path)
    return [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in text]



def _iter_json_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_json_strings(item)



def official_targets_uses_mutable_refs(path: Path | None = None) -> list[str]:
    target = path or OFFICIAL_TARGETS_PATH
    if not target.exists():
        return []
    payload = load_json(target)
    mutable: list[str] = []
    for item in _iter_json_strings(payload):
        if '/blob/main/' in item or '/raw/main/' in item:
            mutable.append(item)
    return mutable



def tracked_junk_files(root: Path | None = None) -> list[str]:
    base = root or ROOT
    hits: list[str] = []
    for path in base.rglob('*'):
        if path.is_dir() and path.name in JUNK_DIR_NAMES:
            hits.append(str(path.relative_to(base)))
        elif path.is_file() and path.name in JUNK_FILE_NAMES:
            hits.append(str(path.relative_to(base)))
    return sorted(hits)



def public_snapshot_candidates() -> list[Path]:
    roots = [PUBLIC_OPENCLAW_SNAPSHOTS, PUBLIC_OPENVIKING_SNAPSHOTS]
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        out.extend(sorted(p for p in root.rglob('*') if p.is_file()))
    return out



def iter_required_template_vars() -> Iterable[str]:
    return iter(sorted(template_required_env_vars()))
