from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def evaluate_experiment(run_dir: Path, exit_code: int) -> dict[str, Any]:
    result_path = run_dir / "experiment_result.json"
    stderr = (run_dir / "stderr.txt").read_text(encoding="utf-8") if (run_dir / "stderr.txt").exists() else ""
    stdout = (run_dir / "stdout.txt").read_text(encoding="utf-8") if (run_dir / "stdout.txt").exists() else ""
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        result = {"success": False, "error": "缺少 experiment_result.json"}

    success = exit_code == 0 and bool(result.get("success"))
    policy_ok = bool(result.get("policy_checked")) and "DASHSCOPE_API_KEY" not in stdout and "DASHSCOPE_API_KEY" not in stderr
    recommend_promotion = success and policy_ok and not stderr.strip()
    report = {
        "success": success,
        "policy_ok": policy_ok,
        "recommend_promotion": recommend_promotion,
        "result": result,
        "stderr_preview": stderr[:1000],
    }
    (run_dir / "experiment_evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "experiment_report.md").write_text(_format_report(report), encoding="utf-8")
    return report


def _format_report(report: dict[str, Any]) -> str:
    result = report.get("result", {})
    return f"""# 沙箱实验报告

## 实验结论

- 是否执行成功：{report.get("success")}
- 沙箱策略通过：{report.get("policy_ok")}
- 是否建议提升：{report.get("recommend_promotion")}

## 关键指标

```json
{json.dumps(result.get("metric_delta", {}), ensure_ascii=False, indent=2)}
```

## 风险检查

- stderr 摘要：{report.get("stderr_preview") or "无"}
- 是否只在沙箱目录内产出：是
- 是否直接修改正式代码：否

## 后续建议

若建议提升为 `True`，请先人工审查 `promotion_proposal.md`，再决定是否修改正式代码。
"""
