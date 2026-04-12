# 一屏内可复制命令

## 初始化

```bash
cp .env.example .env
./scripts/fetch_upstreams.sh
./scripts/setup_envs.sh
openclaw onboard
./scripts/record_versions.sh
./scripts/preflight.sh
python3 scripts/status_matrix.py
```

## 阶段 A：row1 / row3 冒烟

```bash
./scripts/phase_a_smoke.sh
```

如果脚本提示你先手动执行 `ov-install`，就按提示做：

```bash
./scripts/install_openviking_helper.sh
export OPENVIKING_PYTHON="$PWD/.venv-ov/bin/python"
export OPENVIKING_ARK_API_KEY='你的 ark key'
ov-install
./scripts/configure_openviking_local.sh
./scripts/phase_a_smoke.sh
```

## 阶段 B：row1 / row3 全量 + 合并 + judge + summary

```bash
./scripts/phase_b_full_core_and_ov.sh
```

## 阶段 C：row2 LanceDB

```bash
./scripts/phase_c_row2.sh
```

## 阶段 D：row4 调查

```bash
./scripts/row4_probe.sh
```

## 随时查看当前进度

```bash
python3 scripts/status_matrix.py
```

## 打包调试信息

```bash
./scripts/collect_debug_bundle.sh
```
