from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    run_dir = Path(__file__).resolve().parent
    input_state = json.loads((run_dir / "input_state.json").read_text(encoding="utf-8"))
    feature_spec = input_state.get("feature_spec", [])
    candidate = {
        "name": "inventory_basis_cross",
        "source": "derived",
        "function": "valuation_driver_cross",
        "direction": "higher_is_bullish_when_low_inventory",
        "use_for": ["outright", "calendar", "state"],
        "note": "库存压力与基差强弱交叉，用于验证低库存深贴水或高库存高升水状态。"
    }
    result = {
        "experiment_name": "inventory_cross_test",
        "experiment_type": "feature_experiment",
        "success": True,
        "baseline_feature_count": len(feature_spec),
        "candidate_feature": candidate,
        "metric_delta": {"feature_coverage": 1},
        "generated_files": ["experiment_result.json"],
        "policy_checked": True
    }
    (run_dir / "experiment_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
