from __future__ import annotations

from pathlib import Path
from _common import ROOT, sha256_file, write_json, utc_now

SNAPSHOTS = [
    {
        'snapshot_id': '75e07d696e0db5923ac767109f920df2fc807888',
        'path': ROOT / 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888',
        'upstream_repo': 'https://github.com/ZaynJarvis/openclaw-eval',
        'ref': '75e07d696e0db5923ac767109f920df2fc807888',
        'scope_note': 'vendored evaluation-critical files: README.md, eval.py, judge.py, judge_util.py, locomo10.json',
        'used_by_groups': ['row1-memory-core', 'row2-memory-lancedb', 'row3-openviking-minus-core', 'row4-compat-primary'],
        'allow_modifications': False,
    },
    {
        'snapshot_id': '6c60a1d2fb2debd5ac990831350e995473feb6e9',
        'path': ROOT / 'vendor/openviking-legacy-plugin/6c60a1d2fb2debd5ac990831350e995473feb6e9',
        'upstream_repo': 'https://github.com/volcengine/OpenViking',
        'ref': '6c60a1d2fb2debd5ac990831350e995473feb6e9',
        'scope_note': 'vendored execution-critical subtree under examples/openclaw-memory-plugin; helper/tests omitted',
        'used_by_groups': ['row3-openviking-minus-core', 'row4-exploratory-legacy-nonslot'],
        'allow_modifications': False,
    },
    {
        'snapshot_id': 'v0.3.5',
        'path': ROOT / 'vendor/openviking-context-engine/v0.3.5',
        'upstream_repo': 'https://github.com/volcengine/OpenViking',
        'ref': 'v0.3.5',
        'scope_note': 'vendored execution-critical subtree under examples/openclaw-plugin; tests/images/setup-helper omitted',
        'used_by_groups': ['row4-compat-primary'],
        'allow_modifications': False,
    },
]

out = {'generated_at': utc_now(), 'snapshots': []}
for snap in SNAPSHOTS:
    files = []
    for path in sorted([p for p in snap['path'].rglob('*') if p.is_file()]):
        files.append({'path': str(path.relative_to(ROOT)), 'sha256': sha256_file(path)})
    out['snapshots'].append({
        'snapshot_id': snap['snapshot_id'],
        'upstream_repo': snap['upstream_repo'],
        'ref': snap['ref'],
        'fetched_at': utc_now(),
        'scope_note': snap['scope_note'],
        'used_by_groups': snap['used_by_groups'],
        'allow_modifications': snap['allow_modifications'],
        'files': files,
    })
write_json(ROOT / 'env/source_manifest.json', out)
print('Source manifest generated: env/source_manifest.json')
