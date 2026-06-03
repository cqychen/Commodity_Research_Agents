from __future__ import annotations

from pathlib import Path
from typing import Any


def write_promotion_proposal(run_dir: Path, evaluation: dict[str, Any]) -> Path:
    result = evaluation.get("result", {})
    recommend = evaluation.get("recommend_promotion", False)
    proposal = f"""# 沙箱实验提升建议

## 建议结论

{'建议进入人工审查，暂不自动合并。' if recommend else '不建议提升到正式代码，先保留归档。'}

## 拟修改文件

- `src/futures_research_agents/nodes/core.py`
- `src/futures_research_agents/models/store.py`
- `src/futures_research_agents/validators/checks.py`

## 实验摘要

- 实验名称：{result.get('experiment_name', '')}
- 实验类型：{result.get('experiment_type', '')}
- 候选方案：{result.get('candidate_feature') or result.get('candidate_model') or '无'}

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
"""
    path = run_dir / "promotion_proposal.md"
    path.write_text(proposal, encoding="utf-8")
    return path
