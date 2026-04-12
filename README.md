# OpenViking × OpenClaw × LoCoMo10 复现仓库

本仓库对应 `repro_spec_v2.md`。目标不是“先跑出一组数”，而是提供一套**可公开审计、可二次复跑、可区分 strict / compatibility / exploratory 声称边界**的复现实验 harness。仓库的科学口径以 `repro_spec_v2.md`、`env/group_definitions.json`、`env/claim_decisions.json` 为准，其中 row4 默认仍按 compatibility 处理，row3 也不会因为工程闭环变完整就自动升级为 strict。

## 范围与口径

主执行线：

- `row1-memory-core`
- `row2-memory-lancedb`
- `row3-openviking-minus-core`
- `row4-compat-primary`

附录线：

- `row4-exploratory-legacy-nonslot`：仅 appendix / exploratory，不进入主结果表

**对外 claim 的唯一真相源是 `env/claim_decisions.json`。** 当前仓库中：

- `row1` / `row2` 为 strict mainline
- `row3` 仍按 compatibility 口径处理
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
python3 scripts/freeze_versions.py   # 必须在正式实验机上执行一次
python3 scripts/preflight.py
```

说明：

- `env/versions_manifest.json` 随仓库提供的是模板占位文件，不会直接作为正式实验 freeze 使用。
- 开始正式实验前，必须在目标实验机上执行 `python3 scripts/freeze_versions.py`，把运行时版本、模型路由、judge freeze 真正捕获到 `env/versions_manifest.json`。
- `python3 scripts/preflight.py` 是静态验收；`python3 scripts/preflight.py --group ... --online` 会额外检查 live runtime architecture / OpenViking health。

## materialize → preflight → run 的闭环

执行链固定为：

```text
materialize -> exports.env -> preflight -> probe / micro / extended / full
```

这里的 `materialize` 是**显式且不可漂移**的冻结步骤：

- 它会把模板渲染为 `runtime_configs/<run_id>/<group>/openclaw.json`
- 若该组需要 OpenViking，也会生成 `runtime_configs/<run_id>/<group>/ov.conf`
- 它会生成 `runtime_configs/<run_id>/<group>/exports.env`
- 它会写出 `runtime_configs/<run_id>/<group>/materialization_manifest.json`

后续的 `preflight-group`、`probe`、`micro`、`extended`、`full` **只消费已经生成好的 `exports.env`**，不会隐式 rematerialize，也不会静默覆盖已有 `runtime_configs/<run_id>/<group>`。如果要重做同一 `run_id/group`，请显式使用新的 `RUN_ID`，或直接调用 `python3 scripts/materialize_configs.py ... --force`。

## 常用命令

先显式 materialize：

```bash
make materialize GROUP=row3-openviking-minus-core RUN_ID=row3-preflight-001
make preflight-group GROUP=row3-openviking-minus-core RUN_ID=row3-preflight-001
make preflight-group-online GROUP=row3-openviking-minus-core RUN_ID=row3-preflight-001
```

再执行 probe / smoke / full：

```bash
make probe GROUP=row1-memory-core RUN_ID=row1-probe-001
make micro GROUP=row1-memory-core RUN_ID=row1-smoke-001
make extended GROUP=row1-memory-core RUN_ID=row1-smoke-002
make full GROUP=row1-memory-core RUN_ID=row1-full-001
make judge GROUP=row1-memory-core RUN_ID=row1-full-001 MODE=full
make finalize GROUP=row1-memory-core RUN_ID=row1-full-001 MODE=full
make summary
```

也可直接调用 wrapper，但前提仍然是先 `materialize`，并导入这次 run 对应的 `exports.env`：

```bash
python3 scripts/materialize_configs.py <group> <run_id>
export REPRO_RUNTIME_ENV_FILE=runtime_configs/<run_id>/<group>/exports.env

./scripts/run_probe.sh <group> <run_id>
./scripts/run_smoke.sh <group> <run_id> micro
./scripts/run_smoke.sh <group> <run_id> extended
./scripts/run_full_group.sh <group> <run_id>
./scripts/run_judge.sh <group> <run_id> full
```

如果想“一键准备”，可以用：

```bash
make prepare-group GROUP=row1-memory-core RUN_ID=row1-preflight-001
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
- `finalize_group.py` 会把 runtime architecture proof、tail literal、user pattern、gateway-only 约束一起纳入 invalidity

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
pytest -q
python3 scripts/build_benchmark.py
python3 scripts/generate_source_manifest.py
python3 scripts/preflight.py
```

仓库附带最小 CI，会跑：

- `pytest -q`
- `python scripts/build_benchmark.py`
- `python scripts/generate_source_manifest.py`
- `python scripts/preflight.py`

## 可选分析

下面两个脚本不属于最小交付物，但保留用于辅助检查计划第 1 节与第 11 节：

```bash
python3 scripts/build_claim_readiness.py
python3 scripts/build_repeatability_report.py
```
