# OpenViking-OpenClaw-LoCoMo10-Reproduction

这个仓库现在已经从“只准备数据”扩成了“可以直接按步骤执行的复现实验脚手架”。

## 当前目标

先复现两组最关键、也是公开资料最容易严格对齐的实验：

1. `OpenClaw(memory-core)`
2. `OpenClaw + OpenViking Plugin (-memory-core)`

先不把 `memory-lancedb` 和 `(+memory-core)` 混进第一阶段：

- `memory-lancedb` 近期在公开 issue 里有人报告过安装/依赖问题。
- `(+memory-core)` 在当前公开文档里存在 slot 排他带来的配置歧义。

## 当前数据状态

数据已经准备好，主输入文件固定为：

- `data/openviking-locomo10-1540/locomo10_openviking_1540.json`

该数据集来自 pinned 的 `openclaw-eval` LoCoMo10 快照，去除了 `category == 5` 后，保留 **1540** 条 QA case。
详细统计见：

- `data/openviking-locomo10-1540/manifest.json`

## 仓库新增内容

### 目录

- `third_party/`：放上游仓库
- `scripts/`：一键脚本和工具脚本
- `runs/smoke/`：单样本冒烟结果
- `runs/full/`：全量结果
- `artifacts/`：汇总产物
- `logs/`：控制台日志

### 脚本

- `scripts/fetch_upstreams.sh`：拉取上游仓库并固定 `openclaw-eval` commit
- `scripts/setup_envs.sh`：安装 OpenClaw、创建两套 Python 环境
- `scripts/record_versions.sh`：记录版本信息到 `artifacts/versions.txt`
- `scripts/configure_memory_core.sh`：切到 `memory-core`
- `scripts/install_openviking_helper.sh`：安装 OpenViking helper，并提示执行 `ov-install`
- `scripts/configure_openviking_local.sh`：把 OpenClaw 切到 `memory-openviking`（Local mode）
- `scripts/smoke_row1_memory_core.sh`：row1 单样本冒烟
- `scripts/smoke_row3_openviking_minus_core.sh`：row3 单样本冒烟
- `scripts/run_full_group.sh`：按 group 跑 10 个 sample 的 ingest + qa
- `scripts/merge_answers.py`：合并所有 `qa.txt.1.jsonl`
- `scripts/sum_input_tokens.py`：加总每个 group 的输入 token
- `scripts/judge_group.sh`：调用 `judge.py` 生成评分
- `scripts/check_dataset.py`：再次验证本地数据集统计

## 目录结构

```text
.
├── .env.example
├── .gitignore
├── Makefile
├── artifacts/
├── data/
│   └── openviking-locomo10-1540/
├── dataset.sh
├── logs/
├── runs/
│   ├── full/
│   └── smoke/
├── scripts/
└── third_party/
```

## 0. 先复制环境变量模板

```bash
cp .env.example .env
```

至少先填这几个：

- `OPENCLAW_GATEWAY_TOKEN`
- `OPENVIKING_ARK_API_KEY`
- `JUDGE_BASE_URL`
- `JUDGE_API_KEY`
- `JUDGE_MODEL`

如果你的 Python 命令不是默认的 `python3.13` / `python3.10`，也要在 `.env` 里改：

- `EVAL_PYTHON`
- `OV_PYTHON`

## 1. 拉取上游仓库

```bash
./scripts/fetch_upstreams.sh
```

这会做两件事：

- 把 `openclaw-eval` 拉到 `third_party/openclaw-eval`
- 把它固定到 `75e07d696e0db5923ac767109f920df2fc807888`
- 把 `OpenViking` 拉到 `third_party/OpenViking`

## 2. 安装环境

```bash
./scripts/setup_envs.sh
```

这一步会：

- 安装 `openclaw@2026.3.11`
- 在 `third_party/openclaw-eval/.venv` 创建 Python 3.13 环境
- 在仓库根目录 `.venv-ov` 创建 Python 3.10+ 环境，并安装 `openviking==0.1.18`

### 然后手动执行一次

```bash
openclaw onboard
```

这里要你自己选择底层 provider / model，并把生成模型固定成你要复现的那一套。

## 3. 记录版本

```bash
./scripts/record_versions.sh
cat artifacts/versions.txt
```

## 4. 先验证数据

```bash
python3 scripts/check_dataset.py
```

如果输出里看到：

- `sample_count=10`
- `total_after=1540`
- `category_5_present=False`

就说明本地数据仍然是正确的。

## 5. 跑 row1 冒烟

```bash
./scripts/smoke_row1_memory_core.sh
```

成功标志：

- 目录 `runs/smoke/row1-memory-core/` 出现 `ingest.txt`、`qa.txt`、`qa.txt.1.jsonl`
- `qa.txt` 末尾有 `input_tokens / output_tokens / total_tokens`

## 6. 安装并配置 OpenViking 旧版 memory plugin（Local mode）

先装 helper：

```bash
./scripts/install_openviking_helper.sh
```

然后按提示执行：

```bash
export OPENVIKING_PYTHON="$PWD/.venv-ov/bin/python"
export OPENVIKING_ARK_API_KEY='你的ark key'
ov-install
```

进入交互后：

- 选择 **local mode**
- 默认路径基本都可以保留
- 填 Ark API key

运行完成后，会生成：

- `~/.openviking/ov.conf`
- `~/.openclaw/openviking.env`

接着把 OpenClaw 切到 `memory-openviking`：

```bash
./scripts/configure_openviking_local.sh
```

## 7. 跑 row3 冒烟

```bash
./scripts/smoke_row3_openviking_minus_core.sh
```

成功标志和 row1 一样。

## 8. 只有在两个冒烟都通过后，再跑全量

### row1 全量

```bash
./scripts/run_full_group.sh row1-memory-core
```

### row3 全量

```bash
./scripts/run_full_group.sh row3-openviking-minus-core
```

## 9. 合并、统计 token、打分

### 合并 answers

```bash
python3 scripts/merge_answers.py row1-memory-core
python3 scripts/merge_answers.py row3-openviking-minus-core
```

### 统计输入 token

```bash
python3 scripts/sum_input_tokens.py row1-memory-core
python3 scripts/sum_input_tokens.py row3-openviking-minus-core
```

### judge

```bash
./scripts/judge_group.sh row1-memory-core
./scripts/judge_group.sh row3-openviking-minus-core
```

## Makefile 快捷命令

```bash
make fetch-upstreams
make setup-envs
make versions
make smoke-row1
make install-ov-helper
make configure-ov-local
make smoke-row3
make full-row1
make full-row3
make merge-row1
make merge-row3
make judge-row1
make judge-row3
```

## 关键注意事项

### 1）`qa` 和 `ingest` 必须显式传同一个 `--user`

上游 `eval.py` 的默认值并不对称。这个仓库里的脚本已经全部显式传了 `USER_ID`，不要再依赖默认值。

### 2）这里复现的是 **旧版** `memory-openviking`

不是新版 `context-engine` 插件。

### 3）先不要碰 row4

当前公开文档里 `memory` slot 是排他的，所以 `OpenViking Plugin (+memory-core)` 暂时不放进第一阶段。

### 4）Local mode 必须先 source `~/.openclaw/openviking.env`

本仓库里相关脚本会自动处理，但前提是 `ov-install` 已经成功执行过一次。

## 推荐执行顺序

```bash
cp .env.example .env
./scripts/fetch_upstreams.sh
./scripts/setup_envs.sh
openclaw onboard
./scripts/record_versions.sh
python3 scripts/check_dataset.py
./scripts/smoke_row1_memory_core.sh
./scripts/install_openviking_helper.sh
# 按提示执行 ov-install
./scripts/configure_openviking_local.sh
./scripts/smoke_row3_openviking_minus_core.sh
# 两个冒烟都稳了，再跑全量
```
