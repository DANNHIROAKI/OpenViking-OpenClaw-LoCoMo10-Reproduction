# 上游约束与设计决策

这份仓库把“为什么这样配”集中写在这里，避免你后面忘掉。

## 1. 官方目标表来自哪里

目标表来自 OpenViking 官方 README_CN 的 “OpenClaw 上下文插件详情” 一节。仓库里的 `official_targets.json` 已经把 4 组目标值编码好了。

## 2. 为什么先做 row1 / row3

- row1 是最稳定的基线：`OpenClaw(memory-core)`
- row3 是最核心的方法组：`OpenClaw + OpenViking Plugin (-memory-core)`
- row2 需要额外处理 LanceDB 依赖
- row4 在当前公开文档下存在结构性歧义

## 3. 为什么 OpenClaw 要固定到 2026.3.11

旧版 `memory-openviking` 文档明确提示：`2026.3.12+` 可能出现会话挂起。为了减少无关变量，这份仓库把 OpenClaw 版本固定为 `2026.3.11`。

## 4. 为什么 row3 用旧版 `memory-openviking`

官方目标表对应的不是今天主推的 context-engine 插件说明，而是旧版 memory-plugin 语境。为了和目标实验尽量一致，这份仓库在 row3 里使用 `memory-openviking`。

## 5. 为什么 row2 单独处理

`memory-lancedb` 同样占用 OpenClaw 的 `memory` slot，但它近阶段更容易遇到依赖缺失或扩展目录缺少 `@lancedb/lancedb` 的问题，所以仓库里单独准备了补丁脚本。

## 6. 为什么 row4 不放进主线自动化

因为旧版 `memory-openviking` 自身就是 `kind: "memory"`，而 OpenClaw 当前公开文档中 `memory` slot 是排他的。README_CN 里虽然给出了 `(+memory-core)` 结果，但公开安装路径没有提供无歧义的一键配置，所以这里只保留调查脚本，不把它当主线自动化。

## 7. 为什么要显式传 `--user`

`openclaw-eval` 的 workflow 是“先 ingest，再用同一个 user 跑 qa”。为了避免默认值错位，这份仓库所有运行脚本都固定显式传 `--user`。
