from __future__ import annotations

import argparse
from pathlib import Path

from _common import load_json, path_is_sensitive, run_root

BASE_REQUIRED_GROUP_FILES = [
    'run_spec.json',
    'run_meta.json',
    'config_snapshot.json',
    'config_drift.json',
    'merged_answers.json',
    'qa_token_summary.json',
    'ingest_token_summary.json',
    'pipeline_token_summary.json',
    'run_summary.json',
]
JUDGE_REQUIRED_GROUP_FILES = [
    'judge_run_spec.json',
    'grades.json',
]
REQUIRED_SAMPLE_FILES = [
    'ingest.txt',
    'ingest.txt.json',
    'qa.txt',
    'qa_records.jsonl',
    'ingest.console.log',
    'qa.console.log',
    'sample_run_meta.json',
]
PUBLIC_SNAPSHOT_ROOTS = [
    Path('env/openclaw_config_snapshots'),
    Path('env/openviking_config_snapshots'),
]


def _collect_missing_files(root_path: Path, require_judge: bool) -> list[str]:
    missing: list[str] = []
    required_group_files = list(BASE_REQUIRED_GROUP_FILES)
    if require_judge:
        required_group_files.extend(JUDGE_REQUIRED_GROUP_FILES)
    for name in required_group_files:
        if not (root_path / name).exists():
            missing.append(str(root_path / name))
    for sroot in sorted(root_path.glob('sample_*')):
        for name in REQUIRED_SAMPLE_FILES:
            if not (sroot / name).exists():
                missing.append(str(sroot / name))
    return missing


def _read_public_snapshot_file(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        return path.read_text(encoding='utf-8', errors='replace')


def _public_snapshot_has_unredacted_secret(path: Path) -> bool:
    text = _read_public_snapshot_file(path)
    if '[REDACTED]' in text:
        return False
    lowered = text.lower()
    if 'apikey' in lowered:
        return True
    if 'api_key' in lowered:
        return True
    if '"token"' in lowered:
        return True
    if '"secret"' in lowered:
        return True
    if '"password"' in lowered:
        return True
    return False


def _validate_public_snapshot_contract(root_path: Path) -> list[str]:
    errors: list[str] = []
    config_snapshot = load_json(root_path / 'config_snapshot.json')

    for key in ['openclaw', 'openviking']:
        block = config_snapshot.get(key)
        if not isinstance(block, dict):
            continue

        public_snapshot = block.get('actual_snapshot_public')
        if public_snapshot:
            public_path = Path(public_snapshot)
            if not public_path.exists():
                errors.append(f'missing public snapshot file: {public_path}')
            else:
                if _public_snapshot_has_unredacted_secret(public_path):
                    errors.append(f'public snapshot appears unredacted: {public_path}')

        private_snapshot = block.get('actual_snapshot_private')
        if private_snapshot:
            private_path = Path(private_snapshot)
            if not private_path.exists():
                errors.append(f'missing private raw snapshot file: {private_path}')
            if 'private_snapshots' not in private_path.parts:
                errors.append(f'private raw snapshot stored outside private_snapshots/: {private_path}')

        redaction_applied = block.get('redaction_applied')
        redacted_paths = block.get('redacted_paths', [])
        if public_snapshot and redaction_applied and not redacted_paths:
            errors.append(f'{key} snapshot says redaction_applied=true but redacted_paths is empty')

    for public_root in PUBLIC_SNAPSHOT_ROOTS:
        if not public_root.exists():
            continue
        for path in public_root.rglob('*.actual.json'):
            if _public_snapshot_has_unredacted_secret(path):
                errors.append(f'public snapshot directory contains unredacted actual config: {path}')
    return errors


def _validate_runtime_audit_freeze(root_path: Path, group: str) -> list[str]:
    errors: list[str] = []
    if group != 'row2-memory-lancedb':
        return errors

    config_snapshot = load_json(root_path / 'config_snapshot.json')
    audit_freeze = config_snapshot.get('runtime_audit_freeze', {})
    row2 = audit_freeze.get('row2-memory-lancedb', {})
    required = [
        'lancedb_embedding_provider',
    ]
    missing = [key for key in required if not row2.get(key)]
    if missing:
        errors.append(
            'row2 runtime_audit_freeze missing required fields: ' + ', '.join(missing)
        )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('group')
    parser.add_argument('run_id')
    parser.add_argument('--mode', choices=['smoke', 'full'], required=True)
    parser.add_argument('--stage', default=None)
    parser.add_argument('--require-judge', action='store_true')
    args = parser.parse_args()

    root_path = run_root(args.mode, args.run_id, args.group, args.stage)
    missing = _collect_missing_files(root_path, args.require_judge)

    if missing:
        print('Missing files:')
        for item in missing:
            print(f'  - {item}')
        raise SystemExit(1)

    contract_errors: list[str] = []
    contract_errors.extend(_validate_public_snapshot_contract(root_path))
    contract_errors.extend(_validate_runtime_audit_freeze(root_path, args.group))

    if contract_errors:
        print('Contract violations:')
        for item in contract_errors:
            print(f'  - {item}')
        raise SystemExit(1)

    summary = load_json(root_path / 'run_summary.json')
    print(summary['pipeline_status'])
    if summary.get('invalidity_reasons'):
        print('invalidity_reasons:')
        for reason in summary['invalidity_reasons']:
            print(f'  - {reason}')
    print(f'verified: {root_path}')


if __name__ == '__main__':
    main()