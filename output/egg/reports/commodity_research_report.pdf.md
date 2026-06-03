# 鸡蛋 单品种期货研究报告

## 执行摘要

- 研究模式：`explain-existing`
- 最新方向：`neutral`
- 最佳表达：`outright_or_observe`
- 降级等级：`只观察`
- 品种评分：`73.6`，结论：有条件通过，需要记录风险并继续观察

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
- 执行阻塞数量：1

## 下一步优化建议

- 必须补充：可稳定更新的库存和存栏数据。
- 强烈建议：仓单、基差和期限结构的统一口径数据。
- 可选增强：相关品种成本和替代需求数据。


# 品种评分卡

- 总分：73.6
- 结论：有条件通过，需要记录风险并继续观察

- `data_quality`: 75
- `feature_explainability`: 82
- `leakage_reliability`: 85
- `outright_model_stability`: 70
- `calendar_model_stability`: 70
- `signal_quality`: 72
- `tradability`: 60
- `risk_control`: 70
- `latest_signal_confidence`: 72
- `maintainability`: 80
