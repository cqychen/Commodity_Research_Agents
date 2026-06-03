# 沙箱实验提升建议

## 建议结论

建议进入人工审查，暂不自动合并。

## 拟修改文件

- `src/futures_research_agents/nodes/core.py`
- `src/futures_research_agents/models/store.py`
- `src/futures_research_agents/validators/checks.py`

## 实验摘要

- 实验名称：inventory_cross_test
- 实验类型：feature_experiment
- 候选方案：{'name': 'inventory_basis_cross', 'source': 'derived', 'function': 'valuation_driver_cross', 'direction': 'higher_is_bullish_when_low_inventory', 'use_for': ['outright', 'calendar', 'state'], 'note': '库存压力与基差强弱交叉，用于验证低库存深贴水或高库存高升水状态。'}

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
