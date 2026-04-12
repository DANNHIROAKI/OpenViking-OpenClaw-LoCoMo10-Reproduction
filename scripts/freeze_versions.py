from __future__ import annotations

import os
import subprocess
from typing import Any

from _common import (
    ROOT,
    apply_env_file,
    load_json,
    parse_numeric_version,
    sha256_file,
    utc_now,
    version_matches_exact,
    version_matches_major_minor,
    version_satisfies_min,
    write_json,
)

JUDGE_PY = ROOT / 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge.py'
JUDGE_UTIL_PY = ROOT / 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge_util.py'
CONTEXT_INSTALL_MANIFEST = ROOT / 'vendor/openviking-context-engine/v0.3.5/install-manifest.json'

STRICT_SHARED_TARGETS = {
    'openclaw': '2026.3.11',
    'node': '22.x',
    'python': '3.11.x',
}
ROW3_OPENVIKING_TARGET = '0.1.18'


def cmd_text(cmd: list[str]) -> str | None:
    try:
        cp = subprocess.run(cmd, text=True, capture_output=True, check=True)
        return cp.stdout.strip() or cp.stderr.strip() or None
    except Exception:
        return None



def _check_exact(name: str, observed: str | None, expected: str) -> dict[str, Any]:
    return {
        'name': name,
        'rule': f'exact == {expected}',
        'expected': expected,
        'observed': observed,
        'pass': version_matches_exact(observed, expected),
        'observed_parsed': parse_numeric_version(observed),
    }



def _check_major_minor(name: str, observed: str | None, expected_prefix: str) -> dict[str, Any]:
    return {
        'name': name,
        'rule': f'series == {expected_prefix}',
        'expected': expected_prefix,
        'observed': observed,
        'pass': version_matches_major_minor(observed, expected_prefix),
        'observed_parsed': parse_numeric_version(observed),
    }



def _check_min(name: str, observed: str | None, minimum: str) -> dict[str, Any]:
    return {
        'name': name,
        'rule': f'>= {minimum}',
        'expected': minimum,
        'observed': observed,
        'pass': version_satisfies_min(observed, minimum),
        'observed_parsed': parse_numeric_version(observed),
    }



def _model_route_block() -> dict[str, Any]:
    block = {
        'provider': os.environ.get('OPENCLAW_MODEL_PROVIDER') or None,
        'api_base': os.environ.get('OPENCLAW_MODEL_API_BASE') or None,
        'deployment_or_endpoint_id': os.environ.get('OPENCLAW_MODEL_DEPLOYMENT_ID') or None,
        'model': os.environ.get('OPENCLAW_MODEL_ID', 'seed-2.0-code') or 'seed-2.0-code',
        'temperature': os.environ.get('OPENCLAW_MODEL_TEMPERATURE') or None,
        'max_tokens': os.environ.get('OPENCLAW_MODEL_MAX_TOKENS') or None,
        'reasoning': os.environ.get('OPENCLAW_MODEL_REASONING') or None,
    }
    required = ['provider', 'api_base', 'deployment_or_endpoint_id', 'model']
    missing = [field for field in required if not block.get(field)]
    block['required_fields'] = required
    block['missing_required_fields'] = missing
    block['complete_for_formal_runs'] = len(missing) == 0
    return block



def _group_ready_payload(*, group: str, checks: list[dict[str, Any]], model_route: dict[str, Any], notes: list[str] | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    reasons = []
    for item in checks:
        if not item['pass']:
            reasons.append(f"{item['name']} failed rule {item['rule']} (observed={item['observed']!r})")
    if not model_route['complete_for_formal_runs']:
        reasons.append('resolved_model_freeze is incomplete: missing ' + ', '.join(model_route['missing_required_fields']))
    payload: dict[str, Any] = {
        'group': group,
        'checks': checks,
        'model_route_complete': model_route['complete_for_formal_runs'],
        'model_route_missing_fields': model_route['missing_required_fields'],
        'ready_for_formal_wrapper': len(reasons) == 0,
        'blocking_reasons': reasons,
        'notes': notes or [],
    }
    if extra:
        payload.update(extra)
    return payload



def _build_group_readiness(observed: dict[str, str | None], model_route: dict[str, Any], plugin_runtime_constraints: dict[str, Any]) -> dict[str, Any]:
    strict_shared_checks = [
        _check_exact('openclaw', observed.get('openclaw'), STRICT_SHARED_TARGETS['openclaw']),
        _check_major_minor('node', observed.get('node'), STRICT_SHARED_TARGETS['node']),
        _check_major_minor('python', observed.get('python'), STRICT_SHARED_TARGETS['python']),
    ]

    row3_checks = strict_shared_checks + [
        _check_exact('openviking_runtime', observed.get('openviking_runtime'), ROW3_OPENVIKING_TARGET),
    ]

    row4_min = plugin_runtime_constraints.get('row4_context_engine_snapshot_min_openviking_version') or '0.2.9'
    row4_checks = strict_shared_checks + [
        _check_min('openviking_runtime', observed.get('openviking_runtime'), row4_min),
    ]

    readiness: dict[str, Any] = {}
    readiness['row1-memory-core'] = _group_ready_payload(
        group='row1-memory-core',
        checks=list(strict_shared_checks),
        model_route=model_route,
        notes=[
            'row1 does not require OpenViking to be installed to execute, but shared environment freeze still records the common target runtime set.',
        ],
        extra={'claim_track': 'strict-mainline'},
    )
    readiness['row2-memory-lancedb'] = _group_ready_payload(
        group='row2-memory-lancedb',
        checks=list(strict_shared_checks),
        model_route=model_route,
        notes=[
            'row2 is a strict-mainline LanceDB baseline; OpenViking runtime is not execution-critical for this group.',
        ],
        extra={'claim_track': 'strict-mainline'},
    )
    readiness['row3-openviking-minus-core'] = _group_ready_payload(
        group='row3-openviking-minus-core',
        checks=row3_checks,
        model_route=model_route,
        notes=[
            'row3 uses the vendored legacy memory-openviking path and therefore requires the historical OpenViking 0.1.18 runtime freeze.',
        ],
        extra={'claim_track': 'strict-candidate-with-legacy-runtime'},
    )

    official_gap = None
    if observed.get('openviking_runtime'):
        if not version_matches_exact(observed.get('openviking_runtime'), ROW3_OPENVIKING_TARGET):
            official_gap = {
                'official_readme_openviking_version': ROW3_OPENVIKING_TARGET,
                'observed_openviking_runtime': observed.get('openviking_runtime'),
                'mismatch': True,
            }
        else:
            official_gap = {
                'official_readme_openviking_version': ROW3_OPENVIKING_TARGET,
                'observed_openviking_runtime': observed.get('openviking_runtime'),
                'mismatch': False,
            }
    readiness['row4-compat-primary'] = _group_ready_payload(
        group='row4-compat-primary',
        checks=row4_checks,
        model_route=model_route,
        notes=[
            'row4-compat-primary follows the current public context-engine path; runtime readiness is checked against that snapshot\'s minimum OpenViking version rather than the official README\'s 0.1.18.',
            'A passing row4 compatibility readiness check does not erase the historical-version structural gap recorded elsewhere in the repo.',
        ],
        extra={
            'claim_track': 'compatibility-mainline',
            'snapshot_min_openviking_version': row4_min,
            'official_version_gap': official_gap,
        },
    )

    readiness['row4-exploratory-legacy-nonslot'] = {
        'group': 'row4-exploratory-legacy-nonslot',
        'ready_for_formal_wrapper': False,
        'blocking_reasons': ['manual-only exploratory track; mainline wrapper execution is intentionally disabled'],
        'notes': ['Exploratory appendix only.'],
        'claim_track': 'exploratory-appendix-only',
        'checks': [],
        'model_route_complete': model_route['complete_for_formal_runs'],
        'model_route_missing_fields': model_route['missing_required_fields'],
    }
    return readiness



def main() -> None:
    apply_env_file()
    manifest = load_json(ROOT / 'env/versions_manifest.json')
    observed = {
        'openclaw': cmd_text(['openclaw', '--version']),
        'node': cmd_text(['node', '-v']),
        'python': cmd_text(['python3', '--version']),
    }
    ov_python = os.environ.get('OPENVIKING_PYTHON', 'python3')
    observed['openviking_runtime'] = cmd_text([ov_python, '-c', "import openviking,sys;print(getattr(openviking,'__version__','unknown'))"])

    manifest['capture_status'] = 'captured'
    manifest['captured_at'] = utc_now()
    manifest['observed_versions'] = observed

    model_route = _model_route_block()
    manifest['resolved_model_freeze'] = model_route

    judge_model = os.environ.get('JUDGE_MODEL', 'gpt-4o-mini') or 'gpt-4o-mini'
    manifest['judge_freeze'] = {
        'model': judge_model,
        'temperature': 0,
        'response_protocol': 'json_via_prompt',
        'snapshot_files': {
            'judge.py': {
                'path': 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge.py',
                'sha256': sha256_file(JUDGE_PY),
            },
            'judge_util.py': {
                'path': 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/judge_util.py',
                'sha256': sha256_file(JUDGE_UTIL_PY),
            },
        },
        'judge_model_changed': judge_model != 'gpt-4o-mini',
    }

    plugin_runtime_constraints = {
        'row4_context_engine_snapshot_min_openviking_version': None,
        'row4_context_engine_snapshot_min_openclaw_version': None,
    }
    if CONTEXT_INSTALL_MANIFEST.exists():
        install_manifest = load_json(CONTEXT_INSTALL_MANIFEST)
        compatibility = install_manifest.get('compatibility', {})
        plugin_runtime_constraints = {
            'row4_context_engine_snapshot_min_openviking_version': compatibility.get('minOpenvikingVersion'),
            'row4_context_engine_snapshot_min_openclaw_version': compatibility.get('minOpenclawVersion'),
        }
    manifest['plugin_runtime_constraints'] = plugin_runtime_constraints

    manifest['runtime_alignment'] = {
        'shared_target_versions': STRICT_SHARED_TARGETS,
        'row3_openviking_runtime_target': ROW3_OPENVIKING_TARGET,
        'row4_context_engine_snapshot_min_openviking_version': plugin_runtime_constraints.get('row4_context_engine_snapshot_min_openviking_version'),
        'row4_context_engine_snapshot_min_openclaw_version': plugin_runtime_constraints.get('row4_context_engine_snapshot_min_openclaw_version'),
        'model_route_complete': model_route['complete_for_formal_runs'],
        'model_route_missing_fields': model_route['missing_required_fields'],
    }
    manifest['group_readiness'] = _build_group_readiness(observed, model_route, plugin_runtime_constraints)

    manifest['notes'] = [
        'Re-run python3 scripts/freeze_versions.py after filling .env to refresh this manifest for the formal experiment host.',
        'The script stores both target values and observed local versions.',
        'Judge freeze is treated as part of the environment freeze.',
        'Mainline wrappers consult env/versions_manifest.json group_readiness and refuse execution when the target group is not ready.',
    ]

    write_json(ROOT / 'env/versions_manifest.json', manifest)
    print('Versions manifest captured: env/versions_manifest.json')


if __name__ == '__main__':
    main()
