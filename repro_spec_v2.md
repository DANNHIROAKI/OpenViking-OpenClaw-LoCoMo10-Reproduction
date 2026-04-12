# OpenViking × OpenClaw × LoCoMo10 官方结果复现实验计划 v2

> 本版直接替代你当前草稿，目标不是“跑出一组数”，而是产出一套可公开审计、可二次复跑、可区分 strict / compatibility / exploratory 声称边界的复现实验包。

---

## 0. 文档定位与声称边界

本计划把“复现”拆成三类声称，避免把结构不等价的系统跑成假复现：

- **strict reproduction（严格复现）**：版本、数据、插件路径、评测脚本、关键运行参数都被固定，且公开证据足以说明该组与官方口径一致。
- **compatibility reproduction（兼容复现）**：功能上可运行、结构上有公开依据，但路径与官方历史实现不完全同构。
- **exploratory reproduction（探索性复现）**：为了澄清结构歧义而做的工程实验，不得写成“官方结果已严格复现”。

本计划的默认目标是：

- **row1 / row2 / row3 争取 strict**；
- **row4 默认进入 compatibility 轨道**，除非后续拿到足够证据证明其历史共存路径是公开、未改码、且可唯一定位的。

---

## 1. 复现目标

目标对应官方公开的 4 组实验：

| 组别 | 官方任务完成率 | 官方输入 token 总计 |
|---|---:|---:|
| row1 = OpenClaw(memory-core) | 35.65% | 24,611,530 |
| row2 = OpenClaw + LanceDB (-memory-core) | 44.55% | 51,574,530 |
| row3 = OpenClaw + OpenViking Plugin (-memory-core) | 52.08% | 4,264,396 |
| row4 = OpenClaw + OpenViking Plugin (+memory-core) | 51.23% | 2,099,622 |

复现成功分 4 层判定：

### 1.1 流程成功

- 10 个 sample 全部跑通；
- 过滤后 **1540** 条 QA 全部有输出；
- 原始 ingest / qa / judge / 日志 / 配置快照齐全；
- 每组都能从原始文件独立重算完成率与 token 汇总。

### 1.2 方向成功

- 完成率满足 `row3 > row2 > row1`；
- OpenViking 组的可见 input token 明显低于 row1 / row2；
- row4 若执行，则必须与其 claim class 一起解释，不能裸写进 strict 主表。

### 1.3 数值成功

对 **strict 候选组（row1 / row2 / row3）**：

- 完成率与官方差值不超过 **±3.0 个百分点**；
- token 不只给一个数，而是同时给出两套可见账本（见第 10 节）；
- 若两套可见账本中至少有一套与官方差值不超过 **±25%**，则记为“token 口径一致性通过”；
- 若两套都偏离超过 25%，必须在 `deviation_report.md` 中解释差异来源。

### 1.4 可公开声称成功

只有满足以下 3 条，才允许在最终报告首页写“严格复现”：

- 该组被归类为 strict；
- 流程成功 + 方向成功 + 数值成功同时满足；
- 所有版本、脚本、配置、数据快照、日志和 hash 都可被第三方复核。

---

## 2. 公开事实与由此引出的约束

### 2.1 官方表的公开信息

官方 README 给出的这组实验信息至少固定了 5 件事：

- 数据：LoCoMo10，去掉 category 5 后是 **1540** 条 case；
- 实验确实包含 “是否保留 OpenClaw 原生记忆” 两条 OpenViking 组；
- OpenViking 版本写的是 **0.1.18**；
- 任务模型写的是 **seed-2.0-code**；
- 评测脚本指向 **ZaynJarvis/openclaw-eval**。

### 2.2 OpenClaw 插件架构的公开约束

OpenClaw 的 `memory` 与 `contextEngine` 都是 **exclusive slot**；默认 `memory = memory-core`，默认 `contextEngine = legacy`。因此：

- `memory-openviking` 若作为 `kind: "memory"` 占用 memory slot，就会替换掉 `memory-core`；
- 当前新版 `openviking` 插件则是 `kind: "context-engine"`，它走的是另一条架构路径。

### 2.3 旧插件与新插件不能混口径

当前公开安装文档明确说明：

- 新版 `openviking`（context-engine）与旧版 `memory-openviking` **不兼容，不能混装**；
- 旧版 `memory-openviking` 在 OpenClaw `2026.3.12` 上存在已知“对话卡死”问题，公开 workaround 是回退到 **OpenClaw 2026.3.11**。

所以，任何把“旧 memory-openviking 路径”和“新 openviking context-engine 路径”混成同一组的做法，都是不合理的。

### 2.4 openclaw-eval 里的隐性变量必须被显式冻结

公开的评测脚本和 README 暗含了几个会实质改变结果的参数：

- README 的示例命令使用了 `--tail "[remember what's said, keep existing memory]"`；
- 但 CLI 默认 `--tail` 实际是 `[]`；
- README 明确说 QA 阶段需要复用 ingest 阶段同一个 `--user`；
- 但 `eval.py` 默认 ingest user 是 `eval-1`，QA 默认 user 是 `eval-{sample_idx}`；
- `eval.py` 会过滤掉 category 5；
- `eval.py` 的 `--parallel` 默认是 `1`；
- `eval.py --viking` 会绕开 OpenClaw gateway，直接用 `ov add-memory` 写入 OpenViking。

因此，**user、tail、parallel、是否走 gateway** 都不能再依赖默认值，必须写进规格。

---

## 3. 复现主线与附录线

### 3.1 strict 主线

主线只包含：

- row1 = OpenClaw(memory-core)
- row2 = OpenClaw + LanceDB (-memory-core)
- row3 = OpenClaw + OpenViking Plugin (-memory-core)

### 3.2 compatibility 线

- row4 = OpenClaw + OpenViking Plugin (+memory-core)

row4 默认是 compatibility 线，不默认进入 strict 主表。

### 3.3 exploratory 线

任何需要满足以下任一条件的实验，都只能算 exploratory：

- 改动 legacy `memory-openviking` 的 plugin manifest / `kind`；
- 改动 plugin 代码，使其不再占用 memory slot；
- 修改 vendored `eval.py` / `judge.py` 的核心逻辑；
- 在没有公开历史证据的情况下，凭猜测重造一个“row4 历史实现”。

---

## 4. Source freeze：先冻结源码快照，再跑实验

这是本版最关键的补强点。

### 4.1 必须 vendoring 的对象

建立如下目录：

```text
vendor/
  openclaw-eval/<snapshot_id>/
    README.md
    eval.py
    judge.py
    judge_util.py
    locomo10.json
  openviking-legacy-plugin/<snapshot_id>/
    ... legacy memory-openviking source snapshot ...
  openviking-context-engine/<snapshot_id>/
    examples/openclaw-plugin/... (仅 row4 compatibility 用)
```

### 4.2 每个 vendored snapshot 必须记录

`source_manifest.json` 至少记录：

- 上游仓库 URL；
- commit SHA / tag / 可唯一定位的源标识；
- 抓取日期；
- 每个文件的 SHA256；
- 该 snapshot 用于哪些组别；
- 是否允许改动（默认 **不允许**）。

### 4.3 严格禁止追踪 mutable main

- 不允许直接从 `main` 分支安装并把结果写进正式实验；
- 不允许只记“版本号”而不记源码 snapshot；
- 不允许在 full run 期间更新 vendored 内容。

### 4.4 row3 的 strict 先决条件

row3 只有在以下条件满足时，才保留 strict 候选资格：

- 能找到**公开可定位**的 legacy `memory-openviking` 源码 snapshot；
- 能证明该 snapshot 与官方表对应的是同一条 legacy 集成路径；
- 实验安装时使用该 vendored snapshot，而不是当前 main 上的 context-engine 插件。

如果做不到，就把 row3 降级为 compatibility，而不是硬声称 strict。

---

## 5. Canonical benchmark：数据包也要冻结

### 5.1 输入源

本计划的 canonical 输入，不使用“某人本地改过的 LoCoMo10”，而使用 **pinned openclaw-eval snapshot 中 vendored 的 `locomo10.json`** 作为评测输入基线。

原因：

- 官方公开的评测脚本仓库本身就带这个 `locomo10.json`；
- 该文件与脚本、judge、格式化逻辑天然配套；
- 这比“只说基于 LoCoMo10”更可复核。

### 5.2 benchmark 构建产物

```text
benchmark/
  locomo10_raw.json
  locomo10_filtered_no_cat5.json
  locomo10_filtered_no_cat5.jsonl
  manifest.json
```

### 5.3 过滤规则

过滤规则必须与 vendored `eval.py` 一致：

- 保留 `category != 5` 的 QA；
- 保留原 sample 顺序；
- 不手工改 QA 文本、answer、evidence。

### 5.4 manifest.json 必须包含

- 原始文件 SHA256；
- 过滤后文件 SHA256；
- sample 顺序；
- 原始 QA 总数（应为 1986）；
- 过滤后 QA 总数（应为 1540）；
- 过滤后各 category 计数；
- 每个 sample 的 QA 数量；
- 生成脚本版本与生成时间。

**注意：过滤后 category 计数必须程序自动生成，不再手填。**

---

## 6. 环境冻结规范

### 6.1 统一运行时版本

主线统一冻结为：

- **OpenClaw = 2026.3.11**
- **OpenViking runtime = 0.1.18**
- **Node.js = 22.x**
- **Python = 3.11.x**

说明：

- row3 使用 legacy `memory-openviking` 时，OpenClaw 必须保持在 `2026.3.11`；
- 即使当前文档对新版插件只要求 `OpenClaw >= 2026.3.7`，主线仍统一锁 `2026.3.11`，避免跨组引入 OpenClaw 自身行为差异。

### 6.2 模型冻结

- **任务模型目标口径**：`seed-2.0-code`
- 由于 `eval.py` 调的是 `model = "openclaw"`，真正要冻结的是 **OpenClaw gateway 背后的 provider + resolved deployment / endpoint / model id**。
- 不允许写“latest”“默认配置”“自动路由到某 provider”。

必须记录：

- provider 名称；
- `api_base`；
- resolved deployment / endpoint id；
- 实际模型名；
- 温度、max token、reasoning 开关等可能影响结果的参数。

### 6.3 Judge 冻结

judge 也必须冻结为 vendored snapshot：

- `judge.py`
- `judge_util.py`
- grading prompt
- judge model

主 judge：

- 默认 `gpt-4o-mini`
- `temperature = 0`
- JSON grading 输出

若因环境原因替换 judge 模型，只能在 **full run 开始前一次性确定**，并在报告首页标注：

- `judge_model_changed = true`
- 该组不再声称与官方 judge 完全同口径。

### 6.4 OpenViking 配置冻结

若使用 local mode，则 `ov.conf` 内至少冻结：

- `vlm.provider / model / api_key source / api_base`
- `embedding.dense.provider / model / api_key source / api_base / dimension`
- `server.port`
- workspace path
- 任意影响 recall / capture / commit 的参数

### 6.5 默认值禁止隐式继承

凡是插件或服务端配置，只要会影响结果，就必须 materialize 到快照里，不能依赖“当前默认值”。

特别是 row4 compatibility 若走当前 `openviking` context-engine 路径，必须显式写死当前插件相关开关，不能依赖新版 release 中变化过的默认值。

---

## 7. 四个实验组的最终定义

## 7.1 row1：OpenClaw(memory-core) 〔strict 候选〕

定义：

- `plugins.slots.memory = memory-core`
- `plugins.slots.contextEngine = legacy`
- 不安装 OpenViking
- 不安装 LanceDB

用途：官方基线。

## 7.2 row2：OpenClaw + LanceDB (-memory-core) 〔strict 候选〕

定义：

- `plugins.slots.memory = memory-lancedb`
- `plugins.slots.contextEngine = legacy`
- `autoRecall = true`
- `autoCapture = true`
- LanceDB 路径独立
- embedding provider / model / baseURL / dimension 全量固定

用途：传统向量库基线。

## 7.3 row3：OpenClaw + OpenViking Plugin (-memory-core) 〔strict 候选，前提见 4.4〕

定义：

- 使用 **legacy `memory-openviking`** 路径
- `plugins.slots.memory = memory-openviking`
- `plugins.slots.contextEngine = legacy`
- `autoRecall = true`
- `autoCapture = true`
- OpenViking 运行在 local mode
- OpenViking workspace 按 `run_id/group` 隔离

**重要：row3 的 strict 身份来自“legacy plugin 占用 memory slot”的历史路径，而不是当前 `openviking` context-engine。**

## 7.4 row4：OpenClaw + OpenViking Plugin (+memory-core) 〔compatibility 默认轨道〕

### row4-compat-primary（推荐）

定义：

- `plugins.slots.memory = memory-core`
- `plugins.slots.contextEngine = openviking`
- 使用当前公开 `openviking` context-engine 插件
- OpenViking local mode
- 所有 plugin config 显式 materialize

解释：

- 这是**当前公开架构下**唯一有明确文档支撑的共存方式；
- 它能够让 `memory-core` 与 `contextEngine=openviking` 同时处于活动状态；
- 但它不是 legacy `memory-openviking` 路径，因此默认只能记为 compatibility，而非 strict。

### row4-exploratory-legacy-nonslot（可选，不入主表）

定义：

- 基于 vendored legacy `memory-openviking` 做 manifest / kind 改造，使其不再占用 `memory` exclusive slot；
- 与 `memory-core` 共存；
- 仅用于结构探索。

解释：

- 该方案涉及改码或改 manifest；
- 即使跑通，也**永远不能升级为 strict**；
- 只能写入 exploratory appendix。

### row4 的最终记账规则

- `results_summary.md` 中 row4 默认标记为 **compatibility**；
- 只有拿到公开历史证据，证明某条未改码路径就是官方 row4 的实现，才允许单独升级其 claim class；
- 在没有这类证据前，不允许对外说“row4 已严格复现”。

---

## 8. Harness 运行规则（这是正式实验的硬约束）

### 8.1 正式结果只允许走 OpenClaw gateway

正式结果统一要求：

- ingest 走 OpenClaw gateway
- qa 走 OpenClaw gateway
- judge 走 vendored judge

### 8.2 `--viking` 禁止进入主结果

`eval.py --viking` 会直接用 `ov add-memory` 写入 OpenViking，而不是调用 OpenClaw gateway。

因此：

- 它不能代表 row3 / row4 的正式结果；
- 它没有完整、同口径的 gateway usage；
- 最多只能用于本地调试或 exploratory 验证。

### 8.3 user 必须显式传，不得吃脚本默认值

固定规则：

```text
user_id = repro-<run_id>-<group>-sample-<sample_idx>
```

并要求：

- ingest 显式 `--user user_id`
- qa 显式 `--user user_id`

禁止依赖上游默认值。

### 8.4 parallel 固定

正式实验固定：

- `parallel = 1`
- 调用时也必须显式传 `-p 1`

理由不是因为默认值不对，而是为了避免 wrapper 或未来脚本改动后行为漂移。

### 8.5 tail 固定

本计划将主线 ingest tail 固定为：

```text
[remember what's said, keep existing memory]
```

理由：

- 这是上游 `openclaw-eval` README 的显式运行示例；
- 该参数会影响 ingest 时对记忆行为的提示；
- 它不能再依赖 CLI 默认的 `[]`。

同时要求：

- 在 `spec freeze` 阶段把这个 literal 直接写进 `repro_spec_v2.md`；
- 用同一个 literal 跑 row1 / row2 / row3 / row4-compat-primary；
- 另做一组 **2-sample tail sensitivity appendix**，比较 `[]` 与上述 literal 的差异，但不并入主结果。

### 8.6 wrapper 只能“传参”，不能“改逻辑”

允许写一个外层 wrapper 来：

- 统一生成 user id
- 统一传 `--tail`
- 统一传 `-p 1`
- 汇总输出文件

但 **不允许** 修改 vendored `eval.py` / `judge.py` 的以下逻辑：

- message formatting
- category 5 过滤逻辑
- session reset 逻辑
- usage 解析逻辑
- grading prompt

---

## 9. 存储与目录隔离规范

建议目录：

```text
repro/
  vendor/
  benchmark/
  env/
    versions_manifest.json
    source_manifest.json
    openclaw_config_snapshots/
    openviking_config_snapshots/
  storage/
    <run_id>/<group>/...
  runs/
    smoke/<group>/sample_<idx>/...
    full/<group>/sample_<idx>/...
  reports/
```

硬约束：

- 每个 `run_id` 独立；
- row2 的 LanceDB 路径独立；
- row3 / row4 的 OpenViking workspace 独立；
- 不在同一工作目录里混跑不同组；
- 不复用旧 run 的数据库、workspace、sessions、cache；
- 如需重跑，只能从 clean state 重开同组。

---

## 10. Token 记账规范（本版做了关键修正）

官方 README 只写了 “输入 token（总计）”，但没有公开说明是否包含 ingest。

因此本版**不再强行把官方表映射为单一账本**，而是统一输出三列：

### 10.1 QA 可见账本

```text
qa_input_tokens_total
```

定义：

- 只累计 QA 阶段每一问的 `usage.input_tokens`

### 10.2 Ingest 可见账本

```text
ingest_input_tokens_total
```

定义：

- 只累计 ingest 阶段每个 session 的 `usage.input_tokens`

### 10.3 Visible pipeline 账本

```text
visible_pipeline_input_tokens_total = qa_input_tokens_total + ingest_input_tokens_total
```

### 10.4 正式报告的比较方式

最终 summary 表同时显示：

- 官方 `input_tokens_total`
- `qa_input_tokens_total`
- `visible_pipeline_input_tokens_total`
- 两者各自相对官方的差值百分比

### 10.5 隐藏成本说明

对 OpenViking 组，以下成本通常不会完整体现在 gateway usage 中：

- memory extract 的 VLM 调用
- embedding 调用
- OpenViking 内部检索或压缩的服务端成本

因此最终报告必须单独写明：

- “本表中的 token 为 OpenClaw gateway 可见 token，而非系统总成本”。

---

## 11. 每组实验的统一验证梯度

## Step 0：静态验收

每组执行前必须记录：

- source snapshot id
- OpenClaw 版本
- OpenViking 版本
- Node / Python 版本
- model / endpoint / deployment
- OpenClaw config snapshot
- OpenViking config snapshot
- plugin inventory (`openclaw plugins list --json`)
- relevant plugin inspect 输出

## Step 1：功能 probe

每组都做真实 probe，不接受只看进程存活：

- 用全新 probe user 注入 3 条事实；
- 追加 3 个回忆型问题；
- 至少 2/3 正确；
- QA usage 非零。

额外要求：

- row3 / row4 必须有 OpenViking `/health` 正常；
- row3 / row4 必须在日志中看到 capture / recall 迹象；
- row4-compat-primary 必须证明 `memory-core` 与 `contextEngine=openviking` 同时处于活动配置。

## Step 2：micro smoke

- sample 0
- 全部 sessions ingest
- 前 10 个 QA

通过条件：

- 无持续空回答；
- QA usage 可汇总；
- 输出文件完整；
- 结构与计数正确。

## Step 3：extended smoke

- sample 0 + sample 1
- 全部 sessions ingest
- 全量 QA

通过条件：

- 无挂死；
- 无结构性 token=0；
- 两个 sample 的 merge、judge、token 汇总流程完整跑通。

## Step 4：full run #1

- 10 个 sample
- 1540 个 QA
- ingest 和 qa 复用同一 user
- `-p 1`
- 不允许中途升级组件或改配置

## Step 5：repeatability run

- row1：必须做 full run #2
- row3：必须做 full run #2
- row2：建议做 full run #2
- row4：compatibility 组可做 1 次 full run；若结果波动大，可追加一次验证，但不纳入 strict 稳定性统计

---

## 12. Run invalidity：什么情况视为无效 run

满足任一条，该组当前 run 直接判无效：

- benchmark 计数不是 1540；
- ingest 与 qa user 不一致；
- 正式组误用了 `--viking`；
- full run 中 `parallel != 1`；
- 组内配置 hash 中途变化；
- OpenViking group 在正式 QA 中持续出现 usage 缺失 / 全 0；
- 结果文件缺失；
- plugin slot 与组别定义不一致；
- 行为上已明显跑成了另一种架构路径（例如把 row3 跑成了 context-engine）。

### rerun 规则

- 单个 sample 因**基础设施错误**（端口占用、网络错误、写文件失败）可 clean rerun 1 次；
- 若是配置错误、版本漂移、脚本参数错误，必须整组重新开始；
- rerun 也必须保留原始失败日志，不能覆盖。

---

## 13. 全局执行顺序

### Phase A：spec freeze

输出：

- `repro_spec_v2.md`
- `source_manifest.json`

必须写死：

- 组别定义
- claim class
- 数据口径
- versions
- model / judge
- tail literal
- token 账本规则
- invalidity 规则

### Phase B：构建 benchmark

输出：

- `benchmark/manifest.json`

完成标志：

- 原始 1986 QA 与过滤后 1540 QA 都被程序验证通过。

### Phase C：冻结环境

输出：

- `env/versions_manifest.json`
- `env/openclaw_config_snapshots/...`
- `env/openviking_config_snapshots/...`

### Phase D：row1 与 row3 优先

固定顺序：

1. row1 probe
2. row1 micro smoke
3. row1 extended smoke
4. row3 probe
5. row3 micro smoke
6. row3 extended smoke
7. row1 full #1
8. row3 full #1
9. row1 full #2
10. row3 full #2

这样可以最快回答“OpenViking 是否相对 memory-core 更强且更省 token”。

### Phase E：row2

固定顺序：

1. row2 probe
2. row2 micro smoke
3. row2 extended smoke
4. row2 full #1
5. row2 full #2（建议）

### Phase F：row4 compatibility

固定顺序：

1. row4-compat-primary probe
2. row4-compat-primary micro smoke
3. row4-compat-primary extended smoke
4. row4-compat-primary full #1
5. （可选）row4-exploratory-legacy-nonslot appendix

### Phase G：judge 与人工审计

- 主 judge 跑全部有效组别；
- 每个有效组按 category 分层抽样 **100 条** 做人工复核；
- 若 judge 与人工抽检偏差显著，必须在最终报告中单列说明。

---

## 14. 最终交付物

最终至少交付以下文件：

- `repro_spec_v2.md`
- `env/source_manifest.json`
- `env/versions_manifest.json`
- `benchmark/manifest.json`
- 各组 `config_snapshot.json`
- 各组每个 sample 的 ingest / qa 原始输出
- 各组 `merged_answers.json`
- 各组 `qa_token_summary.json`
- 各组 `ingest_token_summary.json`
- 各组 `pipeline_token_summary.json`
- 各组 `grades.json`
- `reports/results_summary.csv`
- `reports/results_summary.md`
- `reports/deviation_report.md`
- `reports/manual_audit.md`
- `reports/row4_structural_note.md`

---

## 15. results_summary 主表字段（统一格式）

主表至少包含以下列：

- group
- claim_class (`strict` / `compatibility` / `exploratory`)
- pipeline_status (`valid` / `invalid`)
- completion_rate
- official_input_tokens_total
- qa_input_tokens_total
- visible_pipeline_input_tokens_total
- delta_vs_official_qa
- delta_vs_official_pipeline
- run_id
- snapshot_id
- notes

**禁止**再出现“只给一个 token 总计，但不解释口径”的表。

---

## 16. deviation_report 必答问题

最终 `deviation_report.md` 必须明确回答：

1. 哪些组是 strict，哪些只是 compatibility / exploratory？
2. row3 是否真的是 legacy `memory-openviking` 路径，而不是误跑成 context-engine？
3. row4 是否存在公开、未改码、可唯一定位的 strict 证据？如果没有，为什么只能算 compatibility？
4. 与官方差异主要来自哪里：
   - 模型 endpoint / deployment
   - judge
   - 插件架构
   - 版本
   - tail / user / harness 参数
   - token 记账口径
   - 隐藏成本未计入
5. 哪些差异是“实验误差”，哪些差异是“结构不等价”？

---

## 17. 禁止事项（正式结果一票否决）

以下做法一律禁止进入主结果：

1. 直接追踪 mutable `main` 而不做 vendoring；
2. 只记版本号，不记源码 snapshot / SHA256；
3. ingest 与 qa 使用不同 user；
4. 正式组使用 `eval.py --viking`；
5. full run 开启并发；
6. 不清理旧存储就混跑同组；
7. 中途升级 OpenClaw / OpenViking / plugin 后继续沿用旧结果；
8. 依赖“当前默认值”而不把关键配置 materialize 到快照；
9. 修改 legacy plugin 代码后仍声称 strict；
10. 在 row4 只有 compatibility 证据时，对外宣称“官方 row4 已严格复现”。

---

## 18. 一句话执行顺序

**先冻结源码、再冻结数据、再冻结环境；先拿下 row1/row3，再补 row2；row4 默认按 compatibility 处理，只有拿到公开历史证据才升级 strict。**

这才是一条在当前公开证据下，既稳、又诚实、也真正可审计的复现路线。
