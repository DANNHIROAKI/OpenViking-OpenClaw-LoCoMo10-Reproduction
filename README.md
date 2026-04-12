# OpenViking × OpenClaw × LoCoMo10 复现仓库

本仓库对应 `repro_spec_v2.md`。它的目标不是“先跑出一组数”，而是提供一套**可公开审计、可二次复跑、可区分 strict / compatibility / exploratory 声称边界**的复现实验 harness。

## 范围与口径

本仓库的**主执行线**是：

- `row1-memory-core`
- `row2-memory-lancedb`
- `row3-openviking-minus-core`
- `row4-compat-primary`

另有：

- `row4-exploratory-legacy-nonslot`：仅附录 / exploratory，不进入主结果表

**对外 claim 的唯一真相源是 `env/claim_decisions.json`。**
当前仓库中：

- `row1` / `row2` 为 strict mainline
- `row3` 仍按 **compatibility** 口径处理，不能因为执行主线包含它，就把它自动写成 strict
- `row4-compat-primary` 为 compatibility

## 目录

```text
benchmark/         固定后的 LoCoMo10 数据包与 manifest
env/               组定义、source freeze、versions freeze、配置模板
reports/           报告模板与后续生成结果
runs/              smoke / full 运行输出
runtime_configs/   materialize 生成的实际配置与 exports.env
scripts/           执行与校验脚本
storage/           运行期隔离存储
vendor/            vendored 上游源码快照与 pinned public evidence
```

## 首次使用

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 scripts/build_benchmark.py
python3 scripts/generate_source_manifest.py
python3 scripts/preflight.py
```

说明：

- `env/versions_manifest.json` 随仓库提供的是**模板占位文件**，不会直接用于正式实验。
- 开始正式实验前，必须在目标实验机上执行 `python3 scripts/freeze_versions.py`，把运行时版本、模型路由、judge freeze 真正捕获到 `env/versions_manifest.json`。
- `python3 scripts/preflight.py` 是静态验收；`python3 scripts/preflight.py --group ... --online` 会额外检查 live runtime architecture / OpenViking health。

## materialize → preflight → run 的闭环

本仓库现在的执行链已经固定为：

```text
materialize -> exports.env -> preflight -> probe / micro / extended / full
```

也就是说，下面这些命令会自动：

1. 生成 `runtime_configs/<run_id>/<group>/openclaw.json`
2. 生成 `runtime_configs/<run_id>/<group>/ov.conf`（若该组需要）
3. 生成 `runtime_configs/<run_id>/<group>/exports.env`
4. 通过 `REPRO_RUNTIME_ENV_FILE` 把这次 run 的 actual config path 注入后续脚本

所以**不再需要手工 export `OPENCLAW_CONFIG_PATH` / `OPENVIKING_CONFIG_PATH`**。

## 常用命令

```bash
make benchmark
make source-manifest
make freeze-versions
make preflight
make preflight-group GROUP=row3-openviking-minus-core RUN_ID=row3-preflight-001
make preflight-group-online GROUP=row3-openviking-minus-core RUN_ID=row3-preflight-001

make probe GROUP=row1-memory-core RUN_ID=row1-probe-001
make micro GROUP=row1-memory-core RUN_ID=row1-smoke-001
make extended GROUP=row1-memory-core RUN_ID=row1-smoke-002
make full GROUP=row1-memory-core RUN_ID=row1-full-001
make judge GROUP=row1-memory-core RUN_ID=row1-full-001 MODE=full
make finalize GROUP=row1-memory-core RUN_ID=row1-full-001 MODE=full
make summary
```

也可直接调用 wrapper：

```bash
./scripts/run_probe.sh <group> <run_id>
./scripts/run_smoke.sh <group> <run_id> micro
./scripts/run_smoke.sh <group> <run_id> extended
./scripts/run_full_group.sh <group> <run_id>
./scripts/run_judge.sh <group> <run_id> full
```

前提是你已经先执行过：

```bash
python3 scripts/materialize_configs.py <group> <run_id>
export REPRO_RUNTIME_ENV_FILE=runtime_configs/<run_id>/<group>/exports.env
```

## 建议执行顺序

按 `repro_spec_v2.md` 第 13 节：

1. row1 probe → micro smoke → extended smoke → full #1 → full #2
2. row3 probe → micro smoke → extended smoke → full #1 → full #2
3. row2 probe → micro smoke → extended smoke → full #1 → full #2（建议）
4. row4-compat-primary probe → micro smoke → extended smoke → full #1

## 主线硬约束

- 正式结果只允许通过 OpenClaw gateway
- 正式组禁止 `eval.py --viking`
- ingest 与 QA 必须显式传同一个 user id
- `parallel` 固定为 `1`
- ingest `tail` 固定为 `[remember what's said, keep existing memory]`
- 不复用旧 storage、workspace、session、cache
- 不在 full run 中途改版本、模型路由或配置
- `finalize_group.py` 会把 runtime architecture proof 纳入 invalidity，而不只看配置文件长相

## 结果文件

- 运行输出：`runs/full/<run_id>/<group>/`、`runs/smoke/<run_id>/<group>/<stage>/`
- 运行期存储：`storage/<run_id>/<group>/`
- materialize 输出：`runtime_configs/<run_id>/<group>/`
- 配置快照：`env/openclaw_config_snapshots/`、`env/openviking_config_snapshots/`
- 预检报告：`reports/preflight/<group>/<run_id>.json`
- 主表：`reports/results_summary.{md,csv}`
- 偏差说明：`reports/deviation_report.md`
- 人工审计：`reports/manual_audit.md`
- row4 结构说明：`reports/row4_structural_note.md`

## 测试与 CI

```bash
pytest
python3 scripts/preflight.py
```

仓库附带最小 CI，会跑：

- `pytest`
- `python3 scripts/build_benchmark.py`
- `python3 scripts/generate_source_manifest.py`
- `python3 scripts/preflight.py`

## 可选分析

下面两个脚本不属于最小交付物，但保留用于辅助检查计划第 1 节与第 11 节：

```bash
python3 scripts/build_claim_readiness.py
python3 scripts/build_repeatability_report.py
```
