# 复现方案（保姆级，按阶段执行）

## 你现在所处的位置

数据已经准备完毕，当前最正确的下一步不是直接跑全量，而是先把复现流程拆成 4 个阶段：

- 阶段 A：把 `OpenClaw(memory-core)` 和 `OpenViking Plugin (-memory-core)` 的 smoke 跑通
- 阶段 B：把这两组扩到 10 个 sample 的全量
- 阶段 C：处理 `memory-lancedb` 的安装/依赖问题，再做 row2
- 阶段 D：把 row4 单独作为“历史兼容 / 文档缺口”处理，不和前三组混跑

## 阶段 A：先拿下 row1 和 row3 的 smoke

### A1. 拉上游仓库

```bash
./scripts/fetch_upstreams.sh
```

结果：
- `third_party/openclaw-eval/`
- `third_party/OpenViking/`

### A2. 安装环境

```bash
./scripts/setup_envs.sh
openclaw onboard
./scripts/record_versions.sh
```

你要确认：
- OpenClaw 被固定到 `2026.3.11`
- `third_party/openclaw-eval/.venv` 存在
- `.venv-ov` 存在，且装的是 `openviking==0.1.18`
- `artifacts/versions.txt` 已经写出来

### A3. 预检查

```bash
./scripts/preflight.sh
```

你应该看到：
- 数据统计是 1540
- `.env` 里的关键变量不为空
- `openclaw-eval` checkout 存在
- Python / Node / npm 命令可用

### A4. 跑 row1 冒烟

```bash
./scripts/smoke_row1_memory_core.sh
```

通过标志：
- `runs/smoke/row1-memory-core/ingest.txt`
- `runs/smoke/row1-memory-core/qa.txt`
- `runs/smoke/row1-memory-core/qa.txt.1.jsonl`
- `qa.txt` 里能找到 `input_tokens:`

### A5. 安装旧版 OpenViking helper 并配置 row3

```bash
./scripts/install_openviking_helper.sh
```

然后按脚本提示执行：

```bash
export OPENVIKING_PYTHON="$PWD/.venv-ov/bin/python"
export OPENVIKING_ARK_API_KEY='你的 ark key'
ov-install
```

交互时：
- 选 local mode
- 默认路径基本都保留
- 填 Ark API key

然后切到旧版 memory-openviking：

```bash
./scripts/configure_openviking_local.sh
```

### A6. 跑 row3 冒烟

```bash
./scripts/smoke_row3_openviking_minus_core.sh
```

通过标志与 row1 相同。

## 阶段 B：把 row1 / row3 扩到全量

### B1. 先跑 row1 全量

```bash
./scripts/run_full_group.sh row1-memory-core
```

### B2. 再跑 row3 全量

```bash
./scripts/run_full_group.sh row3-openviking-minus-core
```

每个 sample 都会单独写到：

```text
runs/full/<group>/sample_0/
runs/full/<group>/sample_1/
...
runs/full/<group>/sample_9/
```

### B3. 合并和打分

```bash
python3 scripts/merge_answers.py row1-memory-core --expected 1540
python3 scripts/merge_answers.py row3-openviking-minus-core --expected 1540

python3 scripts/sum_input_tokens.py row1-memory-core
python3 scripts/sum_input_tokens.py row3-openviking-minus-core

./scripts/judge_group.sh row1-memory-core
./scripts/judge_group.sh row3-openviking-minus-core
```

### B4. 生成对比表

```bash
python3 scripts/build_results_table.py
```

输出会写到：
- `artifacts/results-summary.json`
- `artifacts/results-summary.csv`
- `artifacts/results-summary.md`

## 阶段 C：处理 row2（LanceDB）

row2 不建议一开始就跑。先做这几步：

### C1. 打 LanceDB 依赖补丁

```bash
./scripts/patch_memory_lancedb_global.sh
```

这个脚本会尝试：
- 定位全局 `openclaw` 安装目录
- 补 `dist/package.json` 中的 `@lancedb/lancedb` 依赖声明
- 在 `memory-lancedb` 扩展目录里执行 `npm install @lancedb/lancedb`

### C2. 切到 row2 配置

```bash
./scripts/configure_memory_lancedb.sh
```

### C3. 先跑 row2 冒烟

```bash
./scripts/smoke_row2_lancedb.sh
```

### C4. 冒烟稳了再跑全量

```bash
./scripts/run_full_group.sh row2-memory-lancedb
```

然后同样做合并、token 汇总和 judge。

## 阶段 D：row4 单独处理

当前仓库不把 row4 做成“一键自动化”，原因：

- 当前公开文档中，OpenClaw 的 `memory` slot 是排他的
- 旧版 `memory-openviking` 本身也是 `kind: "memory"`
- 所以 README 里的 `(+memory-core)` 与当前公开安装方式存在结构性歧义

详细见：`docs/ROW4_NOTES.zh-CN.md`

## 每个阶段的停点

### 什么时候可以停止在阶段 A

- row1 smoke 通过
- row3 smoke 通过

### 什么时候可以进入阶段 C

- row1 和 row3 的全量都已经完成
- 合并记录数是 1540
- 你已经拿到至少一版 judge 分数和 token 汇总

### 什么时候才值得碰 row4

- row1 / row2 / row3 都已经有可复现结果
- 你准备把 row4 明确写成“历史兼容 / 文档缺口”问题

## 推荐顺序（直接照抄即可）

```bash
cp .env.example .env
./scripts/fetch_upstreams.sh
./scripts/setup_envs.sh
openclaw onboard
./scripts/record_versions.sh
./scripts/preflight.sh
./scripts/smoke_row1_memory_core.sh
./scripts/install_openviking_helper.sh
# 按提示执行 ov-install
./scripts/configure_openviking_local.sh
./scripts/smoke_row3_openviking_minus_core.sh
./scripts/run_full_group.sh row1-memory-core
./scripts/run_full_group.sh row3-openviking-minus-core
python3 scripts/merge_answers.py row1-memory-core --expected 1540
python3 scripts/merge_answers.py row3-openviking-minus-core --expected 1540
python3 scripts/sum_input_tokens.py row1-memory-core
python3 scripts/sum_input_tokens.py row3-openviking-minus-core
./scripts/judge_group.sh row1-memory-core
./scripts/judge_group.sh row3-openviking-minus-core
python3 scripts/build_results_table.py
# 再处理 row2
./scripts/patch_memory_lancedb_global.sh
./scripts/smoke_row2_lancedb.sh
./scripts/run_full_group.sh row2-memory-lancedb
```


## 新增的一键包装脚本

- `./scripts/phase_a_smoke.sh`：把 preflight、row1 smoke、row3 smoke 串起来；如果缺少 `ov-install` 生成的 env 文件，会停下来明确告诉你下一条命令。
- `./scripts/phase_b_full_core_and_ov.sh`：顺序跑 row1 / row3 全量，并自动 merge、sum tokens、judge、生成 summary。
- `./scripts/phase_c_row2.sh`：顺序跑 row2 的 patch、smoke、full、merge、judge、summary。
- `python3 scripts/status_matrix.py`：根据仓库中已经生成的文件，告诉你“当前做到哪一步、下一条最推荐的命令是什么”。
- `./scripts/row4_probe.sh`：不跑 row4，只导出当前 OpenClaw 插件状态，作为后续调查材料。
