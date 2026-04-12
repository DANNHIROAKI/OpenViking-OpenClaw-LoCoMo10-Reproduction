# Manual Audit

本文件对应 `repro_spec_v2.md` 第 13.G 节。

## 工作流

```bash
python3 scripts/generate_manual_audit_sample.py <group> --run-id <run_id>
python3 scripts/summarize_manual_audit.py
```

人工填写字段：

- `human_result`
- `disagreement_reason`

## 规则

- 只审计 `pipeline_status = valid` 的组
- 每个有效组按 category 分层抽样 100 条
- judge 与人工不一致时，必须填写原因

## 汇总表

| group | run_id | audited_cases | agree | disagree | agreement_rate | note |
|---|---|---:|---:|---:|---:|---|
| row1-memory-core |  |  |  |  |  |  |
| row2-memory-lancedb |  |  |  |  |  |  |
| row3-openviking-minus-core |  |  |  |  |  |  |
| row4-compat-primary |  |  |  |  |  |  |

## 系统性偏差记录

在这里记录 judge 可能存在的系统性偏差、人工审计覆盖范围，以及任何需要在最终报告中说明的限制。
