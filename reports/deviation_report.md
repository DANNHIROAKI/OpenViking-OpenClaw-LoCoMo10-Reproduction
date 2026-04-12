# Deviation Report

本文件对应 `repro_spec_v2.md` 第 16 节。full run 完成后，按下面结构填写。

## 1. claim class 结论

- row1-memory-core: strict
- row2-memory-lancedb: strict
- row3-openviking-minus-core: compatibility（在补足公开同源证据前，不升级 strict）
- row4-compat-primary: compatibility
- row4-exploratory-legacy-nonslot: exploratory

## 2. row3 路径确认

说明本次 row3 是否确实运行在 legacy `memory-openviking` 路径，而不是误跑为 `contextEngine = openviking`。

建议引用：

- `env/openclaw_config_snapshots/<run_id>/...`
- `runs/.../config_snapshot.json`
- `runs/.../config_drift.json`
- plugin inventory / inspect 输出

## 3. row4 证据边界

说明 row4 为什么仍然是 compatibility，或在何种公开证据下才能升级。

## 4. 与官方差异的主要来源

逐项说明：

- 模型 endpoint / deployment
- judge
- 插件架构
- 版本
- tail / user / parallel / gateway 规则
- token 记账口径
- gateway 不可见的隐藏成本

## 5. 实验误差 vs 结构不等价

把观察到的偏差分成两类：

- 实验误差
- 结构不等价

## 6. 定量回填

| group | run_id | pipeline_status | completion_rate | qa_input_tokens_total | visible_pipeline_input_tokens_total | note |
|---|---|---|---:|---:|---:|---|
| row1-memory-core |  |  |  |  |  |  |
| row2-memory-lancedb |  |  |  |  |  |  |
| row3-openviking-minus-core |  |  |  |  |  |  |
| row4-compat-primary |  |  |  |  |  |  |
