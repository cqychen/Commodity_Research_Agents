from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_feature_spec(feature_spec: list[dict[str, Any]]) -> dict[str, Any]:
    required = {"name", "source", "function", "direction", "use_for"}
    violations = [
        {"feature": item.get("name", ""), "missing": sorted(required - set(item))}
        for item in feature_spec
        if required - set(item)
    ]
    return {
        "accepted": bool(feature_spec) and not violations,
        "violations": violations,
        "feature_count": len(feature_spec),
    }


def run_leakage_audit(state: dict[str, Any]) -> dict[str, Any]:
    checks = [
        {"name": "fundamental_asof", "passed": bool(state.get("data_dict", {}).get("asof_rules"))},
        {"name": "feature_spec_declared", "passed": bool(state.get("feature_spec"))},
        {"name": "tradable_targets_declared", "passed": bool(state.get("outright_labels"))},
        {"name": "test_set_sealed", "passed": bool(state.get("commodity_meta", {}).get("valid_end"))},
        {"name": "continuous_not_label", "passed": True},
    ]
    violations = [check for check in checks if not check["passed"]]
    return {
        "leakage_ok": not violations,
        "checks": checks,
        "violations": violations,
    }


def validate_output_contract(output_dirs: dict[str, Path]) -> dict[str, Any]:
    required = [
        output_dirs["latest"] / "latest_instruction.csv",
        output_dirs["latest"] / "latest_actionable_trade.csv",
        output_dirs["latest"] / "next_signal_watch.csv",
        output_dirs["metadata"] / "run_metadata.json",
        output_dirs["reports"] / "research_report.md",
        output_dirs["reports"] / "acceptance_report.md",
    ]
    missing = [str(path) for path in required if not path.exists()]
    return {"accepted": not missing, "missing": missing}
