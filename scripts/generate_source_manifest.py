from __future__ import annotations

from pathlib import Path

from _common import ROOT, load_json, sha256_file, utc_now, write_json

REGISTRY_PATH = ROOT / 'env/source_snapshot_registry.json'
MANIFEST_PATH = ROOT / 'env/source_manifest.json'
GENERATED_AT_PATH = ROOT / 'env/source_manifest.generated_at.txt'


def build_manifest() -> dict:
    registry = load_json(REGISTRY_PATH)
    snapshots = []
    for item in registry.get('snapshots', []):
        vendor_root = ROOT / item['vendor_path']
        files = []
        for path in sorted(p for p in vendor_root.rglob('*') if p.is_file()):
            files.append({'path': str(path.relative_to(ROOT)), 'sha256': sha256_file(path)})
        snapshots.append(
            {
                'snapshot_id': item['snapshot_id'],
                'vendor_path': item['vendor_path'],
                'upstream_repo': item['upstream_repo'],
                'ref': item['ref'],
                'ref_kind': item.get('ref_kind'),
                'vendored_at': item['vendored_at'],
                'retrieval_method': item['retrieval_method'],
                'selection_scope': item['selection_scope'],
                'used_by_groups': item['used_by_groups'],
                'allow_modifications': item['allow_modifications'],
                'files': files,
            }
        )
    return {
        'manifest_version': 2,
        'registry_path': 'env/source_snapshot_registry.json',
        'snapshots': snapshots,
    }


def main() -> None:
    manifest = build_manifest()
    write_json(MANIFEST_PATH, manifest, sort_keys=False)
    GENERATED_AT_PATH.write_text(utc_now() + '\n', encoding='utf-8')
    print('Source manifest generated: env/source_manifest.json')


if __name__ == '__main__':
    main()
