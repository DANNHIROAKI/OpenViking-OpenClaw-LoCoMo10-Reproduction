# 执行清单（按顺序勾选）

## 阶段 A：把 row1 / row3 冒烟跑通

- [ ] `cp .env.example .env`
- [ ] 填好 `.env` 中至少这些变量：
  - [ ] `OPENCLAW_GATEWAY_TOKEN`
  - [ ] `OPENVIKING_ARK_API_KEY`
  - [ ] `JUDGE_BASE_URL`
  - [ ] `JUDGE_API_KEY`
  - [ ] `JUDGE_MODEL`
- [ ] `./scripts/fetch_upstreams.sh`
- [ ] `./scripts/setup_envs.sh`
- [ ] 手动执行一次 `openclaw onboard`
- [ ] `./scripts/record_versions.sh`
- [ ] `./scripts/preflight.sh`
- [ ] `./scripts/smoke_row1_memory_core.sh`
- [ ] `./scripts/install_openviking_helper.sh`
- [ ] 手动执行 `ov-install`（Local mode）
- [ ] `./scripts/configure_openviking_local.sh`
- [ ] `./scripts/smoke_row3_openviking_minus_core.sh`

### 阶段 A 的通过标志

- [ ] `runs/smoke/row1-memory-core/qa.txt.1.jsonl` 存在
- [ ] `runs/smoke/row3-openviking-minus-core/qa.txt.1.jsonl` 存在
- [ ] 两份 `qa.txt` 都能看到 `input_tokens:`

## 阶段 B：跑 row1 / row3 全量

- [ ] `./scripts/run_full_group.sh row1-memory-core`
- [ ] `./scripts/run_full_group.sh row3-openviking-minus-core`
- [ ] `python3 scripts/merge_answers.py row1-memory-core --expected 1540`
- [ ] `python3 scripts/merge_answers.py row3-openviking-minus-core --expected 1540`
- [ ] `python3 scripts/sum_input_tokens.py row1-memory-core`
- [ ] `python3 scripts/sum_input_tokens.py row3-openviking-minus-core`
- [ ] `./scripts/judge_group.sh row1-memory-core`
- [ ] `./scripts/judge_group.sh row3-openviking-minus-core`
- [ ] `python3 scripts/build_results_table.py`

### 阶段 B 的通过标志

- [ ] `artifacts/row1-memory-core.answers.json` 存在且记录数为 1540
- [ ] `artifacts/row3-openviking-minus-core.answers.json` 存在且记录数为 1540
- [ ] `artifacts/row1-memory-core.grades.json` 存在
- [ ] `artifacts/row3-openviking-minus-core.grades.json` 存在
- [ ] `artifacts/results-summary.md` 存在

## 阶段 C：尝试 row2（LanceDB）

- [ ] `.env` 里已填 `LANCEDB_EMBEDDING_API_KEY`
- [ ] `./scripts/patch_memory_lancedb_global.sh`
- [ ] `./scripts/configure_memory_lancedb.sh`
- [ ] `./scripts/smoke_row2_lancedb.sh`
- [ ] `./scripts/run_full_group.sh row2-memory-lancedb`
- [ ] `python3 scripts/merge_answers.py row2-memory-lancedb --expected 1540`
- [ ] `python3 scripts/sum_input_tokens.py row2-memory-lancedb`
- [ ] `./scripts/judge_group.sh row2-memory-lancedb`
- [ ] `python3 scripts/build_results_table.py`

## 阶段 D：row4 只做调查，不在主线中自动化

- [ ] `./scripts/row4_probe.sh`
- [ ] 阅读 `docs/ROW4_NOTES.zh-CN.md`
- [ ] 决定是否将 row4 单独作为“历史兼容 / 文档缺口”写入实验记录
