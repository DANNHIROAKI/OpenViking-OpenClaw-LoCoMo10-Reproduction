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

## 这份仓库现在能做什么

这份仓库已经从“只准备数据”扩成了一套分阶段复现框架：

- 自带过滤后的 LoCoMo10 数据（1540 QA case）
- 固定 `openclaw-eval` 上游 commit
- 创建两套隔离环境：`openclaw-eval` / `OpenViking 0.1.18`
- 跑 3 组主线实验：
  - `row1-memory-core`
  - `row2-memory-lancedb`
  - `row3-openviking-minus-core`
- 合并答案、汇总输入 token、运行 judge、生成对比表
- 把 `row4-openviking-plus-core` 单独保留为调查项，不混入主线自动化

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
│   ├── CHECKLIST.zh-CN.md
│   ├── COMMANDS.zh-CN.md
│   ├── NEXT_STEPS.zh-CN.md
│   ├── PLAN.zh-CN.md
│   ├── ROW4_NOTES.zh-CN.md
│   ├── TROUBLESHOOTING.zh-CN.md
│   └── UPSTREAM_CONSTRAINTS.zh-CN.md
├── logs/
├── runs/
│   ├── full/
│   └── smoke/
├── scripts/
└── third_party/
```

## 你现在该先做什么

先只做 row1 / row3 的 smoke，不要直接跑全量。

### 最短执行路径

```bash
cp .env.example .env
./scripts/bootstrap_once.sh
openclaw onboard
./scripts/record_versions.sh
./scripts/preflight.sh
./scripts/phase_a_smoke.sh
python3 scripts/status_matrix.py
```

如果 `phase_a_smoke.sh` 提示你要先执行 `ov-install`，按提示跑完以后，再重新执行一次它。

## 推荐执行顺序

### 阶段 A：row1 / row3 冒烟

```bash
./scripts/phase_a_smoke.sh
```

### 阶段 B：row1 / row3 全量 + 合并 + judge + summary

```bash
./scripts/phase_b_full_core_and_ov.sh
```

### 阶段 C：row2（LanceDB）

```bash
./scripts/phase_c_row2.sh
```

### 阶段 D：row4 调查

```bash
./scripts/row4_probe.sh
```

## 随时查看“下一步该跑什么”

```bash
python3 scripts/status_matrix.py
```

## 文档导航

- 方案总览：`docs/PLAN.zh-CN.md`
- 现在就照着跑：`docs/NEXT_STEPS.zh-CN.md`
- 一屏内可复制命令：`docs/COMMANDS.zh-CN.md`
- 执行清单：`docs/CHECKLIST.zh-CN.md`
- 上游约束说明：`docs/UPSTREAM_CONSTRAINTS.zh-CN.md`
- row4 为什么不放主线：`docs/ROW4_NOTES.zh-CN.md`
- 常见报错和排查：`docs/TROUBLESHOOTING.zh-CN.md`

## 关键脚本

### 初始化 / 校验

- `scripts/bootstrap_once.sh`
- `scripts/fetch_upstreams.sh`
- `scripts/setup_envs.sh`
- `scripts/record_versions.sh`
- `scripts/preflight.sh`
- `scripts/check_dataset.py`
- `scripts/status_matrix.py`

### 组别配置

- `scripts/configure_memory_core.sh`
- `scripts/configure_memory_lancedb.sh`
- `scripts/patch_memory_lancedb_global.sh`
- `scripts/install_openviking_helper.sh`
- `scripts/configure_openviking_local.sh`

### 运行实验

- `scripts/smoke_row1_memory_core.sh`
- `scripts/smoke_row2_lancedb.sh`
- `scripts/smoke_row3_openviking_minus_core.sh`
- `scripts/run_full_group.sh`
- `scripts/finalize_group.sh`
- `scripts/phase_a_smoke.sh`
- `scripts/phase_b_full_core_and_ov.sh`
- `scripts/phase_c_row2.sh`
- `scripts/row4_probe.sh`

### 汇总与核对

- `scripts/merge_answers.py`
- `scripts/sum_input_tokens.py`
- `scripts/judge_group.sh`
- `scripts/verify_group_outputs.py`
- `scripts/build_results_table.py`
- `scripts/collect_debug_bundle.sh`

## Makefile 快捷命令

```bash
make bootstrap
make fetch-upstreams
make setup-envs
make versions
make preflight
make status
make phase-a
make phase-b
make phase-c
make row4-probe
make summary
```

## 重要注意事项

1. `ingest` 和 `qa` 必须显式传同一个 `--user`。本仓库的运行脚本已经固定这么做。
2. row3 走的是旧版 `memory-openviking` 路径，不是新版 `openviking` context-engine 插件。
3. row2 不建议先于 row1 / row3，因为 `memory-lancedb` 近期更容易卡在依赖和插件加载。
4. row4 目前不做“一键自动化”，原因见 `docs/ROW4_NOTES.zh-CN.md`。
