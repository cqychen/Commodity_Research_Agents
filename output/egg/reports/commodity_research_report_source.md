# 鸡蛋 单品种期货研究报告

## 执行摘要

- 研究模式：`full`
- 最新方向：`long`
- 最佳表达：`calendar_spread`
- 降级等级：`正常交易`
- 品种评分：`76.6`，结论：有条件通过，需要记录风险并继续观察

## 交易假设库

- 低库存 + 深贴水时，期货具备多头赔率。
- 高库存 + 高升水时，期货估值偏高，优先偏空。
- 近远月强弱、季节和年度周期清晰时，跨期表达优先于单边。

## 数据和特征

- as-of 规则：每个信号月只能使用信号日前已经公布的产业数据和当时可见行情。
- FeatureSpec 数量：4
- 特征门禁：True

## 最新交易

- 最新指令：`/home/ubuntu/farmer/china_mm_index/single_commodity_research_agents/output/egg/latest/latest_instruction.csv`
- 当前可执行交易：`/home/ubuntu/farmer/china_mm_index/single_commodity_research_agents/output/egg/latest/latest_actionable_trade.csv`
- 执行阻塞数量：0

## 沙箱实验

- 沙箱 run：`/home/ubuntu/farmer/china_mm_index/single_commodity_research_agents/sandbox/runs/20260603_155600_egg_egg_auto_model_experiment`
- 实验代码：`/home/ubuntu/farmer/china_mm_index/single_commodity_research_agents/sandbox/runs/20260603_155600_egg_egg_auto_model_experiment/experiment_result.json`
- 实验报告：`/home/ubuntu/farmer/china_mm_index/single_commodity_research_agents/sandbox/runs/20260603_155600_egg_egg_auto_model_experiment/experiment_report.md`
- 提升建议：`/home/ubuntu/farmer/china_mm_index/single_commodity_research_agents/sandbox/runs/20260603_155600_egg_egg_auto_model_experiment/promotion_proposal.md`
- 是否建议提升：True

## 下一步优化建议

- 必须补充：可稳定更新的库存和存栏数据。
- 强烈建议：仓单、基差和期限结构的统一口径数据。
- 可选增强：相关品种成本和替代需求数据。


# 品种评分卡

- 总分：76.6
- 结论：有条件通过，需要记录风险并继续观察

- 数据质量（`data_quality`）：85
- 特征解释力（`feature_explainability`）：82
- 防穿越可信度（`leakage_reliability`）：85
- 单边模型稳定性（`outright_model_stability`）：70
- 跨期模型稳定性（`calendar_model_stability`）：70
- 组合信号质量（`signal_quality`）：72
- 交易可执行性（`tradability`）：80
- 风险控制（`risk_control`）：70
- 最新信号可信度（`latest_signal_confidence`）：72
- 可维护性（`maintainability`）：80
