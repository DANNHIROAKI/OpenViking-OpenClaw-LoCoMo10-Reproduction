# row4 说明：为什么这个仓库暂时不把 `OpenViking Plugin (+memory-core)` 做成一键自动化

## 结论

当前公开资料下，row4 不能像 row1 / row2 / row3 那样被无歧义地自动化。

## 原因

### 1. OpenClaw 当前公开文档把 `memory` 定义成排他 slot

这意味着同一时间只能有一个活动的 memory 插件。

### 2. 旧版 `memory-openviking` 本身就是 `kind: "memory"`

也就是说，按照旧版 README 的标准接法，它会直接占用 `plugins.slots.memory`。

### 3. 官方 README_CN 又同时列出了 `(+memory-core)` 这一组

这说明官方历史实验里确实出现过“OpenViking + memory-core 并存”的结果，但当前公开安装路径没有把这件事解释清楚。

## 这份仓库的处理方式

为了让前 3 组先变成可执行、可复核的实验流程，这个仓库采用下面的策略：

- row1 自动化
- row2 自动化（带 LanceDB 补丁脚本）
- row3 自动化
- row4 单独记录为“历史兼容 / 文档缺口”

## 什么时候再来碰 row4

满足以下条件再继续：

1. row1 / row2 / row3 都已经有一版完整结果
2. 你已经把自己的环境版本固定下来
3. 你愿意把 row4 写成“待维护者确认”而不是“官方公开路径可直接复现”

## 如果你一定要探索 row4

建议只把它作为研究性尝试，不要和主复现实验混在一起：

- 路线 A：继续调研维护者对 issue 的回应
- 路线 B：尝试把 OpenViking 改造成非 `memory` slot 的旁路插件
- 路线 C：用新版 `contextEngine` 路径做近似实验，并在报告里明确不是旧版 memory-plugin 的严格复现

## 这份仓库为什么没有给 row4 写 `run_full_group.sh` 分支

因为那样会暗示“这是当前公开文档下的标准路径”，这会误导后续复现实验。
