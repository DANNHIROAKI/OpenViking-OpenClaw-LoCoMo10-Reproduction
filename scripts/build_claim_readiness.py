from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from _common import ROOT, get_claim_decision, official_targets, load_json

REPORT_MD = ROOT / 'reports/claim_readiness.md'
REPORT_CSV = ROOT / 'reports/claim_readiness.csv'



def find_latest_summary(group: str) -> tuple[dict[str, Any] | None, Path | None]:
    candidates = sorted(ROOT.glob(f'runs/full/*/{group}/run_summary.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None, None
    valid = [path for path in candidates if load_json(path).get('pipeline_status') == 'valid']
    chosen = valid[0] if valid else candidates[0]
    return load_json(chosen), chosen



def fmt_pct(value: float | None) -> str:
    if value is None:
        return ''
    return f'{value:.2%}'



def fmt_pp(value: float | None) -> str:
    if value is None:
        return ''
    return f'{value:+.2f}pp'



def fmt_bool(value: bool | None) -> str:
    if value is None:
        return ''
    return 'yes' if value else 'no'



def flow_success(summary: dict[str, Any] | None) -> bool | None:
    if summary is None:
        return None
    return (
        summary.get('pipeline_status') == 'valid'
        and summary.get('sample_count') == 10
        and summary.get('result_count') == 1540
        and summary.get('completion_rate') is not None
    )



def completion_delta_pp(summary: dict[str, Any] | None, official_rate: float) -> float | None:
    if summary is None:
        return None
    measured = summary.get('completion_rate')
    if measured is None:
        return None
    return (measured - official_rate) * 100



def token_delta_ratio(measured: int | None, official_tokens: int) -> float | None:
    if measured is None:
        return None
    return (measured - official_tokens) / official_tokens



def numerical_success(summary: dict[str, Any] | None, official_rate: float, official_tokens: int, target_claim_class: str) -> tuple[bool | None, dict[str, Any]]:
    details: dict[str, Any] = {
        'completion_delta_pp': completion_delta_pp(summary, official_rate),
        'completion_within_3pp': None,
        'qa_token_delta_ratio': None,
        'pipeline_token_delta_ratio': None,
        'token_consistency_pass': None,
    }
    if target_claim_class != 'strict':
        return None, details
    if summary is None or summary.get('pipeline_status') != 'valid':
        return False if summary is not None else None, details

    details['completion_within_3pp'] = details['completion_delta_pp'] is not None and abs(details['completion_delta_pp']) <= 3.0
    qa = summary.get('qa_input_tokens_total')
    pipeline = summary.get('visible_pipeline_input_tokens_total')
    details['qa_token_delta_ratio'] = token_delta_ratio(qa, official_tokens)
    details['pipeline_token_delta_ratio'] = token_delta_ratio(pipeline, official_tokens)
    qa_pass = details['qa_token_delta_ratio'] is not None and abs(details['qa_token_delta_ratio']) <= 0.25
    pipeline_pass = details['pipeline_token_delta_ratio'] is not None and abs(details['pipeline_token_delta_ratio']) <= 0.25
    details['token_consistency_pass'] = qa_pass or pipeline_pass
    return bool(details['completion_within_3pp'] and details['token_consistency_pass']), details



def build_direction_status(summaries: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    row1 = summaries.get('row1-memory-core')
    row2 = summaries.get('row2-memory-lancedb')
    row3 = summaries.get('row3-openviking-minus-core')
    row4 = summaries.get('row4-compat-primary')

    def valid_completion(summary: dict[str, Any] | None) -> float | None:
        if summary is None or summary.get('pipeline_status') != 'valid':
            return None
        return summary.get('completion_rate')

    def valid_pipeline_tokens(summary: dict[str, Any] | None) -> int | None:
        if summary is None or summary.get('pipeline_status') != 'valid':
            return None
        return summary.get('visible_pipeline_input_tokens_total')

    c1, c2, c3, c4 = map(valid_completion, [row1, row2, row3, row4])
    t1, t2, t3, t4 = map(valid_pipeline_tokens, [row1, row2, row3, row4])

    completion_order = None if None in (c1, c2, c3) else (c3 > c2 > c1)
    row3_lower_tokens = None if None in (t1, t2, t3) else (t3 < t1 and t3 < t2)
    row4_lower_tokens = None if None in (t1, t2, t4) else (t4 < t1 and t4 < t2)
    mainline_direction_success = None if completion_order is None or row3_lower_tokens is None else (completion_order and row3_lower_tokens)

    return {
        'completion_order_row3_gt_row2_gt_row1': completion_order,
        'row3_visible_pipeline_lower_than_row1_and_row2': row3_lower_tokens,
        'row4_visible_pipeline_lower_than_row1_and_row2': row4_lower_tokens,
        'mainline_direction_success': mainline_direction_success,
    }



def main() -> None:
    rows: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any] | None] = {}
    paths: dict[str, Path | None] = {}
    for target in official_targets()['rows']:
        summary, path = find_latest_summary(target['group'])
        summaries[target['group']] = summary
        paths[target['group']] = path

    direction = build_direction_status(summaries)

    md_lines = [
        '# Claim Readiness',
        '',
        '> Auto-generated by `python3 scripts/build_claim_readiness.py`.',
        '',
        '## Cross-group direction checks',
        '',
        f"- row3 > row2 > row1 completion order: **{fmt_bool(direction['completion_order_row3_gt_row2_gt_row1']) or 'not available'}**",
        f"- row3 visible pipeline tokens lower than row1/row2: **{fmt_bool(direction['row3_visible_pipeline_lower_than_row1_and_row2']) or 'not available'}**",
        f"- row4 visible pipeline tokens lower than row1/row2: **{fmt_bool(direction['row4_visible_pipeline_lower_than_row1_and_row2']) or 'not available'}**",
        f"- strict-mainline direction success: **{fmt_bool(direction['mainline_direction_success']) or 'not available'}**",
        '',
        '| group | effective_claim_class | flow_success | numerical_success | direction_success | publishable_strict_claim | completion_rate | completion_delta_vs_official | qa_token_delta | pipeline_token_delta | run_id | note |',
        '|---|---|---|---|---|---|---:|---:|---:|---:|---|---|',
    ]

    for target in official_targets()['rows']:
        group = target['group']
        claim = get_claim_decision(group)
        summary = summaries[group]
        flow_ok = flow_success(summary)
        numerical_ok, numerical_details = numerical_success(summary, target['official_completion_rate'], target['official_input_tokens_total'], claim['target_claim_class'])
        if claim['target_claim_class'] == 'strict':
            direction_ok = direction['mainline_direction_success']
        else:
            direction_ok = direction['row4_visible_pipeline_lower_than_row1_and_row2'] if group == 'row4-compat-primary' else None

        publishable_strict_claim = None
        if claim['effective_claim_class'] == 'strict':
            publishable_strict_claim = bool(flow_ok and numerical_ok and direction['mainline_direction_success']) if None not in (flow_ok, numerical_ok, direction['mainline_direction_success']) else None

        row = {
            'group': group,
            'effective_claim_class': claim['effective_claim_class'],
            'flow_success': flow_ok,
            'numerical_success': numerical_ok,
            'direction_success': direction_ok,
            'publishable_strict_claim': publishable_strict_claim,
            'completion_rate': summary.get('completion_rate') if summary else None,
            'completion_delta_vs_official_pp': numerical_details['completion_delta_pp'],
            'qa_token_delta_ratio': numerical_details['qa_token_delta_ratio'],
            'pipeline_token_delta_ratio': numerical_details['pipeline_token_delta_ratio'],
            'run_id': summary.get('run_id') if summary else None,
            'summary_path': str(paths[group].relative_to(ROOT)) if paths[group] else None,
            'note': claim['decision_basis'] if summary is None else '; '.join((summary.get('notes') or []) + (summary.get('invalidity_reasons') or [])),
        }
        rows.append(row)
        md_lines.append(
            '| {group} | {effective_claim_class} | {flow_success} | {numerical_success} | {direction_success} | {publishable_strict_claim} | {completion_rate} | {completion_delta} | {qa_delta} | {pipeline_delta} | {run_id} | {note} |'.format(
                group=row['group'],
                effective_claim_class=row['effective_claim_class'],
                flow_success=fmt_bool(row['flow_success']) or 'not run',
                numerical_success=fmt_bool(row['numerical_success']) or ('n/a' if claim['target_claim_class'] != 'strict' else 'not run'),
                direction_success=fmt_bool(row['direction_success']) or 'not available',
                publishable_strict_claim=fmt_bool(row['publishable_strict_claim']) or ('n/a' if claim['effective_claim_class'] != 'strict' else 'not available'),
                completion_rate=fmt_pct(row['completion_rate']),
                completion_delta=fmt_pp(row['completion_delta_vs_official_pp']),
                qa_delta=fmt_pct(row['qa_token_delta_ratio']),
                pipeline_delta=fmt_pct(row['pipeline_token_delta_ratio']),
                run_id=row['run_id'] or '',
                note=row['note'],
            )
        )

    with REPORT_CSV.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    REPORT_MD.write_text('\n'.join(md_lines) + '\n', encoding='utf-8')
    print(f'Wrote {REPORT_CSV} and {REPORT_MD}')


if __name__ == '__main__':
    main()
