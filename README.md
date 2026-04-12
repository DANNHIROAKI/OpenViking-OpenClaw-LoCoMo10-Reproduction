# OpenViking-OpenClaw-LoCoMo10-Reproduction

这个仓库用于复现 OpenViking 官方 README_CN 中的 LoCoMo10 / OpenClaw 对比实验。

## 目标实验

官方给出的目标结果如下：

| 组别 | 官方任务完成率 | 官方输入 token 总计 |
|---|---:|---:|
| OpenClaw(memory-core) | 35.65% | 24,611,530 |
| OpenClaw + LanceDB (-memory-core) | 44.55% | 51,574,530 |
| OpenClaw + OpenViking Plugin (-memory-core) | 52.08% | 4,264,396 |
| OpenClaw + OpenViking Plugin (+memory-core) | 51.23% | 2,099,622 |

仓库内的 `official_targets.json` 已经把这张表编码好了，后续可以直接生成自己的对比结果表。

## 当前仓库能做什么

这个仓库已经不只是“准备数据”，而是一套按阶段执行的复现实验框架：

- 已包含过滤后的 LoCoMo10 数据（1540 QA case）
- 可以拉取并固定 `openclaw-eval` 上游 commit
- 可以安装两套隔离环境：`openclaw-eval` + `OpenViking 0.1.18`
- 可以自动跑三组实验的 smoke / full：
  - row1: `OpenClaw(memory-core)`
  - row2: `OpenClaw + LanceDB (-memory-core)`
  - row3: `OpenClaw + OpenViking Plugin (-memory-core)`
- 可以汇总 token、合并 answers、运行 judge、生成对比表
- 对 row4 提供了单独说明文档和决策记录

## 目录结构

```text
.
├── .env.example
├── .gitignore
├── Makefile
├── README.md
├── official_targets.json
├── artifacts/
├── data/
│   └── openviking-locomo10-1540/
├── dataset.sh
├── docs/
│   ├── PLAN.zh-CN.md
│   ├── ROW4_NOTES.zh-CN.md
│   └── TROUBLESHOOTING.zh-CN.md
├── logs/
├── runs/
│   ├── full/
│   └── smoke/
├── scripts/
└── third_party/
```

## 先看哪份文档

- 方案总览：`docs/PLAN.zh-CN.md`
- row4 为什么先不自动化：`docs/ROW4_NOTES.zh-CN.md`
- 常见报错和排查：`docs/TROUBLESHOOTING.zh-CN.md`

## 快速开始

### 0. 复制环境变量模板

```bash
cp .env.example .env
```

你至少要先填：

- `OPENCLAW_GATEWAY_TOKEN`
- `OPENVIKING_ARK_API_KEY`
- `JUDGE_BASE_URL`
- `JUDGE_API_KEY`
- `JUDGE_MODEL`
- 如果要跑 row2：`LANCEDB_EMBEDDING_API_KEY`

### 1. 拉上游仓库

```bash
./scripts/fetch_upstreams.sh
```

### 2. 安装环境

```bash
./scripts/setup_envs.sh
openclaw onboard
./scripts/record_versions.sh
```

### 3. 预检查

```bash
./scripts/preflight.sh
```

### 4. 先跑 row1 / row3 冒烟

```bash
./scripts/smoke_row1_memory_core.sh
./scripts/install_openviking_helper.sh
# 按提示执行 ov-install
./scripts/configure_openviking_local.sh
./scripts/smoke_row3_openviking_minus_core.sh
```

### 5. 冒烟稳定后再跑全量

```bash
./scripts/run_full_group.sh row1-memory-core
./scripts/run_full_group.sh row3-openviking-minus-core
```

### 6. 再尝试 row2

```bash
./scripts/patch_memory_lancedb_global.sh
./scripts/smoke_row2_lancedb.sh
./scripts/run_full_group.sh row2-memory-lancedb
```

### 7. 汇总结果

```bash
python3 scripts/merge_answers.py row1-memory-core --expected 1540
python3 scripts/merge_answers.py row3-openviking-minus-core --expected 1540
python3 scripts/merge_answers.py row2-memory-lancedb --expected 1540

python3 scripts/sum_input_tokens.py row1-memory-core
python3 scripts/sum_input_tokens.py row3-openviking-minus-core
python3 scripts/sum_input_tokens.py row2-memory-lancedb

./scripts/judge_group.sh row1-memory-core
./scripts/judge_group.sh row3-openviking-minus-core
./scripts/judge_group.sh row2-memory-lancedb

python3 scripts/build_results_table.py
```

## 脚本说明

### 核心准备

- `scripts/fetch_upstreams.sh`：拉取 `openclaw-eval` 和 `OpenViking`
- `scripts/setup_envs.sh`：安装 OpenClaw、创建两套 venv
- `scripts/record_versions.sh`：写出 `artifacts/versions.txt`
- `scripts/preflight.sh`：检查数据、环境变量、目录和常用命令
- `scripts/diagnose_openclaw.sh`：导出 OpenClaw 状态和插件列表

### 组别切换

- `scripts/configure_memory_core.sh`
- `scripts/configure_memory_lancedb.sh`
- `scripts/patch_memory_lancedb_global.sh`
- `scripts/configure_openviking_local.sh`

### 运行实验

- `scripts/smoke_row1_memory_core.sh`
- `scripts/smoke_row2_lancedb.sh`
- `scripts/smoke_row3_openviking_minus_core.sh`
- `scripts/run_full_group.sh`

### 汇总结果

- `scripts/merge_answers.py`
- `scripts/sum_input_tokens.py`
- `scripts/judge_group.sh`
- `scripts/build_results_table.py`
- `scripts/check_dataset.py`

## Makefile 快捷命令

```bash
make fetch-upstreams
make setup-envs
make versions
make preflight
make diagnose-openclaw
make smoke-row1
make install-ov-helper
make configure-ov-local
make smoke-row3
make patch-row2
make configure-row2
make smoke-row2
make full-row1
make full-row2
make full-row3
make merge-row1
make merge-row2
make merge-row3
make judge-row1
make judge-row2
make judge-row3
make summary
```

## 重要注意事项

1. `ingest` 和 `qa` 必须显式传同一个 `--user`。本仓库里的运行脚本都已经固定这么做。
2. row3 用的是旧版 `memory-openviking` 路径，不是新版 `openviking` context-engine 插件。
3. row2 当前最好放在 row1 / row3 之后，因为 `memory-lancedb` 最近有多条公开 issue 指向依赖缺失或插件无法加载。
4. row4 目前不做“一键自动化”，原因见 `docs/ROW4_NOTES.zh-CN.md`。
