# OpenViking × OpenClaw × LoCoMo10 复现仓库

本仓库对应 `repro_spec_v2.md`。仓库只保留正式复现所需的源码快照、基准数据、配置模板、执行脚本与报告模板。

## 范围

- strict 主线：`row1-memory-core`、`row2-memory-lancedb`、`row3-openviking-minus-core`
- compatibility：`row4-compat-primary`
- exploratory：`row4-exploratory-legacy-nonslot`（仅附录，不进主结果表）

## 目录

```text
benchmark/   固定后的 LoCoMo10 数据包与 manifest
env/         组定义、source freeze、versions freeze、配置模板
reports/     报告模板与后续生成结果
runs/        smoke / full 运行输出
scripts/     执行与校验脚本
storage/     运行期隔离存储
vendor/      vendored 上游源码快照
```

## 首次使用

```bash
cp .env.example .env
python3 scripts/build_benchmark.py
python3 scripts/generate_source_manifest.py
python3 scripts/freeze_versions.py
python3 scripts/preflight.py
python3 scripts/preflight.py --group row1-memory-core
```

说明：`env/versions_manifest.json` 随仓库提供的是模板，占位值不会用于正式实验。开始正式运行前，必须在目标实验机上重新执行 `python3 scripts/freeze_versions.py`。

## 建议执行顺序

按 `repro_spec_v2.md` 第 13 节：

1. row1 probe → micro smoke → extended smoke → full #1 → full #2
2. row3 probe → micro smoke → extended smoke → full #1 → full #2
3. row2 probe → micro smoke → extended smoke → full #1 → full #2（建议）
4. row4-compat-primary probe → micro smoke → extended smoke → full #1

## 常用命令

```bash
make benchmark
make source-manifest
make freeze-versions
make preflight
make preflight-group GROUP=row3-openviking-minus-core
make materialize GROUP=row3-openviking-minus-core RUN_ID=row3-probe-001
make probe GROUP=row1-memory-core RUN_ID=row1-probe-001
make micro GROUP=row1-memory-core RUN_ID=row1-smoke-001
make extended GROUP=row1-memory-core RUN_ID=row1-smoke-002
make full GROUP=row1-memory-core RUN_ID=row1-full-001
make judge GROUP=row1-memory-core RUN_ID=row1-full-001 MODE=full
make summary
```

也可直接调用：

```bash
./scripts/run_probe.sh <group> <run_id>
./scripts/run_smoke.sh <group> <run_id> micro
./scripts/run_smoke.sh <group> <run_id> extended
./scripts/run_full_group.sh <group> <run_id>
./scripts/run_judge.sh <group> <run_id> full
```

## 主线硬约束

- 正式结果只允许通过 OpenClaw gateway
- 正式组禁止 `eval.py --viking`
- ingest 与 QA 必须显式传同一个 user id
- `parallel` 固定为 `1`
- ingest `tail` 固定为 `[remember what's said, keep existing memory]`
- 不复用旧 storage、workspace、session、cache
- 不在 full run 中途改版本、模型路由或配置

## 结果文件

- 运行输出：`runs/full/<run_id>/<group>/`、`runs/smoke/<run_id>/<group>/<stage>/`
- 运行期存储：`storage/<run_id>/<group>/`
- 配置快照：`env/openclaw_config_snapshots/`、`env/openviking_config_snapshots/`
- 主表：`reports/results_summary.{md,csv}`
- 偏差说明：`reports/deviation_report.md`
- 人工审计：`reports/manual_audit.md`
- row4 结构说明：`reports/row4_structural_note.md`

## 可选分析

下面两个脚本不属于最小交付物，但保留用于辅助检查计划第 1 节与第 11 节：

```bash
python3 scripts/build_claim_readiness.py
python3 scripts/build_repeatability_report.py
```
