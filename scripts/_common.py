from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / '.env'
GROUP_DEFS_PATH = ROOT / 'env/group_definitions.json'
CLAIM_DECISIONS_PATH = ROOT / 'env/claim_decisions.json'
OFFICIAL_TARGETS_PATH = ROOT / 'official_targets.json'
BENCHMARK_PATH = ROOT / 'benchmark/locomo10_filtered_no_cat5.json'
BENCHMARK_MANIFEST_PATH = ROOT / 'benchmark/manifest.json'
OPENCLAW_EVAL_DIR = ROOT / 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888'
TAIL_LITERAL = "[remember what's said, keep existing memory]"
PARALLEL = 1

BRACE_PLACEHOLDER_RE = re.compile(r'(?<!\$)\{([A-Za-z_][A-Za-z0-9_]*)\}')
ENV_PLACEHOLDER_RE = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')
_META_KEYS = {'notes', '__repro_meta__', '_repro_meta', '_meta'}
_SENSITIVE_TOKENS = {'api_key', 'apikey', 'token', 'secret', 'password'}
_VERSION_RE = re.compile(r'(\d+(?:\.\d+)+|\d+)')
_ENV_KEY_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_INT_RE = re.compile(r'-?\d+')
_FLOAT_RE = re.compile(r'-?(?:\d+\.\d*|\d*\.\d+)')


def parse_numeric_version(text: str | None) -> tuple[int, ...] | None:
    if not text:
        return None
    match = _VERSION_RE.search(text)
    if not match:
        return None
    try:
        return tuple(int(part) for part in match.group(1).split('.'))
    except Exception:
        return None


def parse_version_pattern(pattern: str | None) -> tuple[int, ...] | None:
    if not pattern:
        return None
    cleaned = pattern.strip().lower()
    if cleaned.endswith('.x'):
        cleaned = cleaned[:-2]
    cleaned = cleaned.rstrip('.')
    if not cleaned:
        return None
    try:
        return tuple(int(part) for part in cleaned.split('.'))
    except Exception:
        return None


def version_matches_exact(text: str | None, expected: str) -> bool:
    actual = parse_numeric_version(text)
    target = parse_version_pattern(expected)
    return actual == target and actual is not None


def version_matches_major_minor(text: str | None, expected_prefix: str) -> bool:
    actual = parse_numeric_version(text)
    target = parse_version_pattern(expected_prefix)
    if actual is None or target is None:
        return False
    return actual[: len(target)] == target


def version_satisfies_min(text: str | None, minimum: str) -> bool:
    actual = parse_numeric_version(text)
    target = parse_version_pattern(minimum)
    if actual is None or target is None:
        return False
    width = max(len(actual), len(target))
    actual_padded = actual + (0,) * (width - len(actual))
    target_padded = target + (0,) * (width - len(target))
    return actual_padded >= target_padded


def versions_manifest() -> dict[str, Any]:
    path = ROOT / 'env/versions_manifest.json'
    if not path.exists():
        return {}
    return load_json(path)


def group_readiness(group: str, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    data = manifest or versions_manifest()
    return (data.get('group_readiness') or {}).get(group, {})


def _strip_wrapping_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_env_assignment(line: str) -> tuple[str, str] | None:
    raw = line.strip()
    if not raw or raw.startswith('#'):
        return None
    if raw.startswith('export '):
        raw = raw[len('export ') :].lstrip()
    if '=' not in raw:
        return None
    key, value = raw.split('=', 1)
    key = key.strip()
    if not _ENV_KEY_RE.fullmatch(key):
        return None
    return key, _strip_wrapping_quotes(value)


def load_env_file(path: Path | None = None) -> dict[str, str]:
    env_path = path or ENV_FILE
    env: dict[str, str] = {}
    if not env_path.exists():
        return env
    for line in env_path.read_text(encoding='utf-8').splitlines():
        parsed = _parse_env_assignment(line)
        if parsed is None:
            continue
        key, value = parsed
        env[key] = value
    return env


def runtime_env_file_path() -> Path | None:
    raw = os.environ.get('REPRO_RUNTIME_ENV_FILE')
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def load_runtime_env_file() -> dict[str, str]:
    path = runtime_env_file_path()
    if path is None:
        return {}
    return load_env_file(path)


def merged_env(
    extra: dict[str, Any] | None = None,
    *,
    base_env: dict[str, Any] | None = None,
) -> dict[str, str]:
    env: dict[str, str] = {}
    env.update(load_env_file())
    env.update(load_runtime_env_file())
    source_env = base_env if base_env is not None else os.environ
    env.update({k: str(v) for k, v in source_env.items()})
    if extra:
        env.update({k: str(v) for k, v in extra.items() if v is not None})
    return env


def apply_env_file(extra: dict[str, Any] | None = None) -> dict[str, str]:
    env = merged_env(extra)
    os.environ.update(env)
    return env


def to_shell_exports(env_map: dict[str, Any]) -> str:
    lines = []
    for key in sorted(env_map):
        value = env_map[key]
        if value is None:
            continue
        lines.append(f'export {key}={shlex.quote(str(value))}')
    return '\n'.join(lines) + ('\n' if lines else '')


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def parse_json_text(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:
        return None


def write_json(path: Path, obj: Any, *, sort_keys: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=sort_keys) + '\n', encoding='utf-8')


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def relpath(path: Path) -> str:
    return str(path.relative_to(ROOT))


def path_label(path: Path) -> str:
    try:
        return relpath(path)
    except Exception:
        return str(path)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_path_absent(path: Path, label: str | None = None) -> None:
    if path.exists():
        prefix = f'{label} already exists' if label else 'path already exists'
        raise FileExistsError(f'{prefix}: {path_label(path)}')


def ensure_fresh_dir(path: Path, label: str | None = None) -> Path:
    ensure_path_absent(path, label)
    path.mkdir(parents=True, exist_ok=False)
    return path


def file_sha_if_exists(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    return sha256_file(path)


def read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return load_json(path)


def _render_string(
    value: str,
    mapping: dict[str, str],
    *,
    expand_env: bool,
    env: dict[str, str] | None,
    strict_mapping: bool,
    strict_env: bool,
) -> str:
    def repl_brace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in mapping:
            return str(mapping[key])
        if strict_mapping:
            raise KeyError(f'missing placeholder value: {{{key}}}')
        return match.group(0)

    rendered = BRACE_PLACEHOLDER_RE.sub(repl_brace, value)
    if not expand_env:
        return rendered

    env_map = merged_env(env)

    def repl_env(match: re.Match[str]) -> str:
        key = match.group(1)
        env_value = env_map.get(key)
        if env_value not in (None, ''):
            return env_value
        if strict_env:
            raise KeyError(f'missing env placeholder value: ${{{key}}}')
        return match.group(0)

    return ENV_PLACEHOLDER_RE.sub(repl_env, rendered)


def render_placeholders(
    value: Any,
    mapping: dict[str, str],
    *,
    expand_env: bool = False,
    env: dict[str, str] | None = None,
    strict_mapping: bool = True,
    strict_env: bool = False,
) -> Any:
    if isinstance(value, str):
        return _render_string(
            value,
            mapping,
            expand_env=expand_env,
            env=env,
            strict_mapping=strict_mapping,
            strict_env=strict_env,
        )
    if isinstance(value, list):
        return [
            render_placeholders(
                item,
                mapping,
                expand_env=expand_env,
                env=env,
                strict_mapping=strict_mapping,
                strict_env=strict_env,
            )
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: render_placeholders(
                item,
                mapping,
                expand_env=expand_env,
                env=env,
                strict_mapping=strict_mapping,
                strict_env=strict_env,
            )
            for key, item in value.items()
        }
    return value


def collect_env_placeholders(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, str):
        out.update(match.group(1) for match in ENV_PLACEHOLDER_RE.finditer(value))
    elif isinstance(value, list):
        for item in value:
            out.update(collect_env_placeholders(item))
    elif isinstance(value, dict):
        for item in value.values():
            out.update(collect_env_placeholders(item))
    return out


def strip_repro_meta(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: strip_repro_meta(item) for key, item in value.items() if key not in _META_KEYS}
    if isinstance(value, list):
        return [strip_repro_meta(item) for item in value]
    return value


def missing_env_vars(value: Any, env: dict[str, str] | None = None) -> list[str]:
    env_map = merged_env(env)
    missing = []
    for key in sorted(collect_env_placeholders(value)):
        if env_map.get(key) in (None, ''):
            missing.append(key)
    return missing


def _path_is_sensitive(path: str) -> bool:
    lowered = path.lower()
    return any(token in lowered for token in _SENSITIVE_TOKENS)


def _coerce_string(value: str, path: str = '') -> Any:
    raw = value.strip()
    if not raw or _path_is_sensitive(path):
        return value
    if ENV_PLACEHOLDER_RE.fullmatch(raw):
        return raw

    lower = raw.lower()
    if lower == 'true':
        return True
    if lower == 'false':
        return False
    if lower == 'null':
        return None

    if raw.startswith('{') or raw.startswith('['):
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        else:
            return coerce_non_sensitive_scalars(parsed, path)

    if _INT_RE.fullmatch(raw):
        try:
            return int(raw)
        except Exception:
            return value
    if _FLOAT_RE.fullmatch(raw):
        try:
            return float(raw)
        except Exception:
            return value
    return value


def coerce_non_sensitive_scalars(value: Any, path: str = '') -> Any:
    if isinstance(value, dict):
        return {
            key: coerce_non_sensitive_scalars(item, f'{path}.{key}' if path else key)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [coerce_non_sensitive_scalars(item, f'{path}[{idx}]') for idx, item in enumerate(value)]
    if isinstance(value, str):
        return _coerce_string(value, path)
    return value


def render_materialized_config(
    template_obj: Any,
    mapping: dict[str, str],
    *,
    env: dict[str, str] | None = None,
    strict_env: bool = True,
) -> Any:
    rendered = render_placeholders(template_obj, mapping, expand_env=True, env=env, strict_env=strict_env)
    rendered = strip_repro_meta(rendered)
    return coerce_non_sensitive_scalars(rendered)


def _leaf_matches(expected: Any, actual: Any, path: str = '') -> bool:
    if isinstance(expected, str) and ENV_PLACEHOLDER_RE.fullmatch(expected):
        return True
    return coerce_non_sensitive_scalars(expected, path) == coerce_non_sensitive_scalars(actual, path)


def subset_mismatches(expected: Any, actual: Any, path: str = '') -> list[str]:
    mismatches: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f'{path or "<root>"}: expected object']
        for key, expected_value in expected.items():
            child_path = f'{path}.{key}' if path else key
            if key not in actual:
                mismatches.append(f'{child_path}: missing key')
                continue
            mismatches.extend(subset_mismatches(expected_value, actual[key], child_path))
        return mismatches

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f'{path or "<root>"}: expected list']
        if len(expected) != len(actual):
            mismatches.append(f'{path or "<root>"}: list length mismatch (expected {len(expected)}, got {len(actual)})')
            return mismatches
        for idx, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            mismatches.extend(subset_mismatches(expected_item, actual_item, f'{path}[{idx}]'))
        return mismatches

    if _leaf_matches(expected, actual, path):
        return []

    if _path_is_sensitive(path):
        return [f'{path or "<root>"}: sensitive value mismatch']
    return [f'{path or "<root>"}: value mismatch (expected {expected!r}, got {actual!r})']


def group_defs() -> dict[str, Any]:
    return load_json(GROUP_DEFS_PATH)


def claim_decisions() -> dict[str, Any]:
    return load_json(CLAIM_DECISIONS_PATH)


def official_targets() -> dict[str, Any]:
    return load_json(OFFICIAL_TARGETS_PATH)


def get_group_spec(group: str) -> dict[str, Any]:
    for item in group_defs()['groups']:
        if item['group'] == group:
            return item
    raise KeyError(f'unknown group: {group}')


def get_claim_decision(group: str) -> dict[str, Any]:
    for item in claim_decisions()['decisions']:
        if item['group'] == group:
            return item
    raise KeyError(f'unknown claim decision: {group}')


def user_id(run_id: str, group: str, sample_idx: int) -> str:
    return group_defs()['user_id_pattern'].format(run_id=run_id, group=group, sample_idx=sample_idx)


def run_root(mode: str, run_id: str, group: str, stage: str | None = None) -> Path:
    if mode == 'full':
        return ROOT / 'runs' / 'full' / run_id / group
    if not stage:
        raise ValueError('stage is required for smoke mode')
    return ROOT / 'runs' / 'smoke' / run_id / group / stage


def sample_root(mode: str, run_id: str, group: str, sample_idx: int, stage: str | None = None) -> Path:
    return run_root(mode, run_id, group, stage) / f'sample_{sample_idx}'


def storage_root(run_id: str, group: str) -> Path:
    return ROOT / 'storage' / run_id / group


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    merged = merged_env(env)
    return subprocess.run(cmd, cwd=cwd, env=merged, text=True, capture_output=True, check=check)


def run_shell(
    command: str,
    *,
    check: bool = False,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        check=check,
        cwd=cwd or ROOT,
        env=merged_env(env),
    )
