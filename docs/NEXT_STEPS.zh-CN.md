# 你现在就按这个顺序跑

## 1. 复制环境变量模板并填写

```bash
cp .env.example .env
```

至少填这些值：

- `OPENCLAW_GATEWAY_TOKEN`
- `OPENVIKING_ARK_API_KEY`
- `JUDGE_BASE_URL`
- `JUDGE_API_KEY`
- `JUDGE_MODEL`
- 如果你准备跑 row2，再补 `LANCEDB_EMBEDDING_API_KEY`

## 2. 先把上游仓库和虚拟环境准备好

```bash
./scripts/bootstrap_once.sh
```

这个脚本会：
- 拉 `openclaw-eval`
- 拉 `OpenViking`
- 安装 OpenClaw `2026.3.11`
- 建两套 venv

## 3. 手动执行一次 OpenClaw onboarding

```bash
openclaw onboard
```

这里要把 OpenClaw 的默认生成模型固定到和你的复现实验一致的模型配置。

## 4. 记录版本并做预检查

```bash
./scripts/record_versions.sh
./scripts/preflight.sh
python3 scripts/status_matrix.py
```

## 5. 先跑 row1 / row3 冒烟

```bash
./scripts/phase_a_smoke.sh
```

如果它提示你先执行 `ov-install`，就按提示执行：

```bash
./scripts/install_openviking_helper.sh
export OPENVIKING_PYTHON="$PWD/.venv-ov/bin/python"
export OPENVIKING_ARK_API_KEY='你的 ark key'
ov-install
./scripts/configure_openviking_local.sh
./scripts/phase_a_smoke.sh
```

## 6. 冒烟过了再跑 row1 / row3 全量

```bash
./scripts/phase_b_full_core_and_ov.sh
```

## 7. 再尝试 row2

```bash
./scripts/phase_c_row2.sh
```

## 8. 只把 row4 当调查项

```bash
./scripts/row4_probe.sh
```

## 9. 任何时候想知道下一步是什么

```bash
python3 scripts/status_matrix.py
```
