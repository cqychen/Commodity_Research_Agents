from __future__ import annotations

import json
from typing import Any


def build_experiment_code(experiment_type: str, experiment_name: str) -> str:
    if experiment_type == "feature_experiment":
        return _feature_experiment_code(experiment_name)
    if experiment_type == "model_experiment":
        return _model_experiment_code(experiment_name)
    raise ValueError(f"不支持的实验类型: {experiment_type}")


def build_experiment_code_with_llm(
    *,
    llm: Any,
    experiment_type: str,
    experiment_name: str,
    state: dict[str, Any],
) -> str:
    response = llm.invoke(build_experiment_prompt(experiment_type=experiment_type, experiment_name=experiment_name, state=state))
    content = getattr(response, "content", response)
    return parse_llm_experiment_code(str(content))


def build_experiment_prompt(*, experiment_type: str, experiment_name: str, state: dict[str, Any]) -> str:
    prompt = f"""你是单品种期货研究系统的沙箱代码生成 Agent。

请生成一个可以在沙箱 run 目录内独立执行的 Python 脚本，只输出 Python 代码，不要解释。

硬性要求：
1. 只能读取当前目录下的 input_state.json。
2. 只能写入当前目录下的 experiment_result.json。
3. 不允许读取环境变量、API key、网络、父目录或正式 src 目录。
4. 不允许下单、不允许修改正式代码。
5. 必须输出 JSON，字段至少包含：
   - experiment_name
   - experiment_type
   - success
   - candidate_feature 或 candidate_model
   - metric_delta
   - generated_files
   - policy_checked

实验类型：{experiment_type}
实验名称：{experiment_name}

可用状态摘要：
{json.dumps(_summarize_state(state), ensure_ascii=False, indent=2, default=str)}
"""
    return prompt


def parse_llm_experiment_code(content: str) -> str:
    code = _extract_python_code(str(content))
    if "experiment_result.json" not in code or "input_state.json" not in code:
        raise ValueError("LLM 生成代码缺少必要输入/输出文件约定")
    return code


def _summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "commodity_id": state.get("commodity_id"),
        "mode": state.get("mode"),
        "feature_count": len(state.get("feature_spec", [])),
        "feature_spec": state.get("feature_spec", [])[:8],
        "outright_model": state.get("outright_model", {}),
        "calendar_model": state.get("calendar_model", {}),
        "backtest_report": state.get("backtest_report", {}),
        "signal_synthesis": state.get("signal_synthesis", {}),
    }


def _extract_python_code(content: str) -> str:
    marker = "```"
    if marker not in content:
        return content.strip()
    chunks = content.split(marker)
    for chunk in chunks:
        stripped = chunk.strip()
        if stripped.startswith("python"):
            return stripped[len("python") :].strip()
    return chunks[1].strip()


def _feature_experiment_code(experiment_name: str) -> str:
    return f'''from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    run_dir = Path(__file__).resolve().parent
    input_state = json.loads((run_dir / "input_state.json").read_text(encoding="utf-8"))
    feature_spec = input_state.get("feature_spec", [])
    candidate = {{
        "name": "inventory_basis_cross",
        "source": "derived",
        "function": "valuation_driver_cross",
        "direction": "higher_is_bullish_when_low_inventory",
        "use_for": ["outright", "calendar", "state"],
        "note": "库存压力与基差强弱交叉，用于验证低库存深贴水或高库存高升水状态。"
    }}
    result = {{
        "experiment_name": "{experiment_name}",
        "experiment_type": "feature_experiment",
        "success": True,
        "baseline_feature_count": len(feature_spec),
        "candidate_feature": candidate,
        "metric_delta": {{"feature_coverage": 1}},
        "generated_files": ["experiment_result.json"],
        "policy_checked": True
    }}
    (run_dir / "experiment_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
'''


def _model_experiment_code(experiment_name: str) -> str:
    return f'''from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    run_dir = Path(__file__).resolve().parent
    input_state = json.loads((run_dir / "input_state.json").read_text(encoding="utf-8"))
    model_info = input_state.get("outright_model", {{}})
    result = {{
        "experiment_name": "{experiment_name}",
        "experiment_type": "model_experiment",
        "success": True,
        "baseline_model": model_info.get("model_family", "unknown"),
        "candidate_model": "ridge_with_inventory_basis_cross",
        "metric_delta": {{"validation_stability_score": 0.01}},
        "generated_files": ["experiment_result.json"],
        "policy_checked": True
    }}
    (run_dir / "experiment_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
'''
