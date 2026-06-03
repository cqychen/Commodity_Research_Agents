from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..config import CommodityConfig


IMPORTANT_OUTPUTS = {
    "latest_instruction": "output/egg_latest_instruction.csv",
    "latest_actionable_trade": "output/egg_latest_actionable_trade.csv",
    "next_signal_watch": "output/egg_next_signal_watch.csv",
    "signal": "output/egg_signal.csv",
    "prediction": "output/egg_prediction.csv",
    "backtest_stats": "output/egg_backtest_stats.csv",
    "single_leg_backtest_stats": "output/egg_single_leg_backtest_stats.csv",
    "state_backtest": "output/egg_state_backtest.csv",
    "strategy_type_backtest": "output/egg_strategy_type_backtest.csv",
    "selected_feature_detail": "output/egg_selected_feature_detail.csv",
    "metadata": "output/egg_metadata.csv",
}


def _read_csv_summary(path: Path, tail_rows: int = 3) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return {"exists": True, "path": str(path), "error": str(exc)}
    return {
        "exists": True,
        "path": str(path),
        "rows": int(len(df)),
        "columns": list(df.columns),
        "tail": df.tail(tail_rows).fillna("").to_dict(orient="records"),
    }


def load_existing_egg_outputs(config: CommodityConfig) -> dict[str, Any]:
    if config.existing_system_path is None:
        return {"existing_system_path": "", "available": False, "outputs": {}}
    base = config.existing_system_path
    outputs = {name: _read_csv_summary(base / rel_path) for name, rel_path in IMPORTANT_OUTPUTS.items()}
    return {
        "existing_system_path": str(base),
        "available": base.exists(),
        "outputs": outputs,
    }


def copy_key_outputs_to_contract(config: CommodityConfig, output_dirs: dict[str, Path]) -> list[str]:
    """Copy existing output files into the new output contract for explain-existing mode."""
    if config.existing_system_path is None:
        return []
    copied: list[str] = []
    mapping = {
        "output/egg_latest_instruction.csv": output_dirs["latest"] / "latest_instruction.csv",
        "output/egg_latest_actionable_trade.csv": output_dirs["latest"] / "latest_actionable_trade.csv",
        "output/egg_next_signal_watch.csv": output_dirs["latest"] / "next_signal_watch.csv",
        "output/egg_signal.csv": output_dirs["tables"] / "signal.csv",
        "output/egg_prediction.csv": output_dirs["tables"] / "outright_prediction.csv",
        "output/egg_backtest_stats.csv": output_dirs["tables"] / "combined_backtest_stats.csv",
        "output/egg_single_leg_backtest_stats.csv": output_dirs["tables"] / "outright_backtest_stats.csv",
        "output/egg_state_backtest.csv": output_dirs["tables"] / "state_backtest.csv",
        "output/egg_strategy_type_backtest.csv": output_dirs["tables"] / "strategy_type_backtest.csv",
        "output/egg_state_aware_backtest.csv": output_dirs["tables"] / "state_aware_backtest.csv",
        "output/egg_target_aligned_backtest.csv": output_dirs["tables"] / "target_aligned_backtest.csv",
        "output/egg_trade_rounds.csv": output_dirs["tables"] / "trade_rounds.csv",
        "output/egg_feature_catalog.csv": output_dirs["tables"] / "feature_catalog.csv",
        "output/egg_selected_feature_detail.csv": output_dirs["tables"] / "selected_feature_detail.csv",
        "output/egg_metadata.csv": output_dirs["metadata"] / "existing_system_metadata.csv",
    }
    for rel_path, dest in mapping.items():
        src = config.existing_system_path / rel_path
        if src.exists():
            dest.write_bytes(src.read_bytes())
            copied.append(str(dest))
    return copied
