# 沙箱实验提升建议

## 建议结论

建议进入人工审查，暂不自动合并。

## 拟修改文件

- `src/futures_research_agents/nodes/core.py`
- `src/futures_research_agents/models/store.py`
- `src/futures_research_agents/validators/checks.py`

## 实验摘要

- 实验名称：egg_auto_model_experiment
- 实验类型：model_experiment
- 候选方案：{'type': 'auto_ensemble', 'features_used': ['inventory_pressure', 'basis_strength', 'profit_cycle', 'hv20_1y_pct'], 'feature_weights': {'inventory_pressure': 0.3, 'basis_strength': 0.3, 'profit_cycle': 0.25, 'hv20_1y_pct': 0.15}, 'target_signals': ['outright', 'calendar'], 'risk_filter_enabled': True, 'lag_handling': 'aligned_by_lag_months'}

## 预期收益

- 增强特征解释或模型稳定性。
- 为后续正式开发提供可复现的实验记录。

## 风险

- 沙箱指标不等于真实样本外收益。
- 合并前必须重新跑防穿越、full 流程和 smoke test。

## 回滚方式

- 不修改正式代码时无需回滚。
- 若后续人工合并，应以单独提交记录变更，并可直接 revert 该提交。

## 测试计划

```bash
PYTHONPATH=src python -m compileall src tests
PYTHONPATH=src python tests/smoke_test.py
PYTHONPATH=src python -m futures_research_agents.cli --commodity egg --mode full --print-summary
```
