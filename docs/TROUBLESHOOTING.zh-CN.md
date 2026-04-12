# Troubleshooting

## 1. `memory-openviking` 打开后对话卡住 / 没响应

优先检查 OpenClaw 版本。

建议：
- 固定 OpenClaw 到 `2026.3.11`
- 不要先装 `2026.3.12+` 再临时切回来

排查命令：

```bash
openclaw --version
openclaw status
./scripts/diagnose_openclaw.sh
```

## 2. `ov-install` 之后还是找不到 `~/.openclaw/openviking.env`

说明 helper 的 local mode 还没完整跑完。

检查：

```bash
ls -lah ~/.openviking/ov.conf
ls -lah ~/.openclaw/openviking.env
```

如果缺失：
- 重新运行 `ov-install`
- 确认交互里选的是 local mode

## 3. row1 / row3 smoke 的 `qa.txt` 里没有 `input_tokens:`

先看日志：

```bash
cat logs/row1-memory-core.sample0.qa.log
cat logs/row3-openviking-minus-core.sample0.qa.log
```

再确认：
- `OPENCLAW_GATEWAY_TOKEN` 是否正确
- Gateway 是否真的跑在 `OPENCLAW_BASE_URL`
- 你的 OpenClaw 生成模型是否已经在 `openclaw onboard` 里配置好

## 4. row2 切到 `memory-lancedb` 后报 `Cannot find module '@lancedb/lancedb'`

先跑补丁脚本：

```bash
./scripts/patch_memory_lancedb_global.sh
```

然后：

```bash
openclaw gateway restart
openclaw plugins list
./scripts/diagnose_openclaw.sh
```

## 5. row2 冒烟还是失败

进一步确认：
- `LANCEDB_EMBEDDING_API_KEY` 已填写
- `LANCEDB_EMBEDDING_MODEL` 是否为支持值
- `openclaw plugins list` 里 `memory-lancedb` 是否显示为 loaded / active

## 6. merge 后不是 1540 条

最常见原因：
- 某个 sample 没跑完
- 某个 `qa.txt.1.jsonl` 被覆盖或缺失
- 某个 group 的 `--user` 没和 ingest 对齐

检查：

```bash
find runs/full/row1-memory-core -name 'qa.txt.1.jsonl' | wc -l
find runs/full/row2-memory-lancedb -name 'qa.txt.1.jsonl' | wc -l
find runs/full/row3-openviking-minus-core -name 'qa.txt.1.jsonl' | wc -l
```

## 7. judge 没法跑

先确认 `.env` 里这三个变量：

- `JUDGE_BASE_URL`
- `JUDGE_API_KEY`
- `JUDGE_MODEL`

然后单独执行：

```bash
./scripts/judge_group.sh row1-memory-core
```

## 8. 想先看 OpenClaw 当前到底加载了什么

```bash
./scripts/diagnose_openclaw.sh
```

会把以下内容导出到 `artifacts/`：
- `openclaw.plugins.list.txt`
- `openclaw.status.txt`
- 尝试读取的 slot 配置
