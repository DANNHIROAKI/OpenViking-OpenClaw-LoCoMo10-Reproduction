from __future__ import annotations

from collections import Counter
from pathlib import Path
import copy
import json
import shutil

from _common import ROOT, OPENCLAW_EVAL_DIR, sha256_file, write_json, utc_now

RAW_PATH = OPENCLAW_EVAL_DIR / 'locomo10.json'
OUT_RAW = ROOT / 'benchmark/locomo10_raw.json'
OUT_FILTERED = ROOT / 'benchmark/locomo10_filtered_no_cat5.json'
OUT_JSONL = ROOT / 'benchmark/locomo10_filtered_no_cat5.jsonl'
OUT_MANIFEST = ROOT / 'benchmark/manifest.json'

raw = json.loads(RAW_PATH.read_text(encoding='utf-8'))
raw_count = 0
filtered_count = 0
category_before = Counter()
category_after = Counter()
sample_order = []
per_sample = []
filtered = []
jsonl_records = []

for sample_idx, item in enumerate(raw):
    sample_order.append(item['sample_id'])
    qas = item.get('qa', [])
    raw_count += len(qas)
    kept = []
    sample_after = Counter()
    for qa_idx, qa in enumerate(qas, start=1):
        cat = str(qa.get('category', ''))
        category_before[cat] += 1
        if cat == '5':
            continue
        category_after[cat] += 1
        sample_after[cat] += 1
        kept.append(copy.deepcopy(qa))
        jsonl_records.append({
            'sample_id': item['sample_id'],
            'sample_idx': sample_idx,
            'qa_idx': qa_idx,
            'category': qa.get('category'),
            'question': qa.get('question'),
            'answer': qa.get('answer'),
            'evidence': qa.get('evidence', []),
        })
    new_item = copy.deepcopy(item)
    new_item['qa'] = kept
    filtered.append(new_item)
    filtered_count += len(kept)
    per_sample.append({
        'sample_id': item['sample_id'],
        'kept_cases': len(kept),
        'category_breakdown': dict(sorted(sample_after.items(), key=lambda kv: kv[0])),
    })

if raw_count != 1986:
    raise SystemExit(f'expected raw_count=1986, got {raw_count}')
if filtered_count != 1540:
    raise SystemExit(f'expected filtered_count=1540, got {filtered_count}')

OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(RAW_PATH, OUT_RAW)
OUT_FILTERED.write_text(json.dumps(filtered, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with OUT_JSONL.open('w', encoding='utf-8') as f:
    for record in jsonl_records:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')

manifest = {
    'generated_at': utc_now(),
    'generator': 'scripts/build_benchmark.py',
    'source': {
        'path': 'vendor/openclaw-eval/75e07d696e0db5923ac767109f920df2fc807888/locomo10.json',
        'sha256': sha256_file(RAW_PATH),
    },
    'files': {
        'locomo10_raw.json': {'path': 'benchmark/locomo10_raw.json', 'sha256': sha256_file(OUT_RAW)},
        'locomo10_filtered_no_cat5.json': {'path': 'benchmark/locomo10_filtered_no_cat5.json', 'sha256': sha256_file(OUT_FILTERED)},
        'locomo10_filtered_no_cat5.jsonl': {'path': 'benchmark/locomo10_filtered_no_cat5.jsonl', 'sha256': sha256_file(OUT_JSONL)},
    },
    'byte_identical_raw_copy': sha256_file(RAW_PATH) == sha256_file(OUT_RAW),
    'sample_order': sample_order,
    'counts': {
        'raw_total_qas': raw_count,
        'filtered_total_qas': filtered_count,
        'category_counts_before_filter': dict(sorted(category_before.items(), key=lambda kv: kv[0])),
        'category_counts_after_filter': dict(sorted(category_after.items(), key=lambda kv: kv[0])),
    },
    'per_sample': per_sample,
    'filter_rule': 'keep QA where str(category) != "5"; preserve original sample order and QA content',
}
write_json(OUT_MANIFEST, manifest)
print(f'Benchmark built: {OUT_MANIFEST}')
