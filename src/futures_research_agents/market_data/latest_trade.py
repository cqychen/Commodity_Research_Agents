from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..config import CommodityConfig
from ..tools.io import write_json
from .tushare_refresh import refresh_tushare_cache


def _last_record(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    return df.tail(1).fillna("").to_dict(orient="records")[0]


def build_latest_trade_files(
    config: CommodityConfig,
    output_dirs: dict[str, Path],
    signal_synthesis: dict[str, Any],
    refresh_market: bool = False,
) -> dict[str, Any]:
    latest_dir = output_dirs["latest"]
    metadata_dir = output_dirs["metadata"]
    tables_dir = output_dirs["tables"]
    project_root = tables_dir.parents[2]
    tushare_metadata: dict[str, Any] | None = None
    if refresh_market:
        tushare_metadata = refresh_tushare_cache(project_root=project_root, config=config, output_dirs=output_dirs)

    existing_instruction = latest_dir / "latest_instruction.csv"
    existing_actionable = latest_dir / "latest_actionable_trade.csv"
    existing_watch = latest_dir / "next_signal_watch.csv"

    signal = pd.read_csv(tables_dir / "signal.csv") if (tables_dir / "signal.csv").exists() else pd.DataFrame()
    latest_signal = _last_record(signal)

    instruction = {
        "commodity_id": config.commodity_id,
        "fut_code": config.fut_code,
        "selected_expression": signal_synthesis.get("selected_expression", "observe"),
        "target_position": signal_synthesis.get("target_position", latest_signal.get("target_position", 0.0)),
        "direction": signal_synthesis.get("direction", "neutral"),
        "degrade_level": signal_synthesis.get("degrade_level", "只观察"),
        "source": "generated_by_latest_trade_agent",
    }

    pd.DataFrame([instruction]).to_csv(existing_instruction, index=False)

    blockers: list[dict[str, Any]] = []
    if instruction["degrade_level"] in {"只观察", "研究中"}:
        blockers.append({"reason": "degraded_signal", "detail": instruction["degrade_level"]})
    if not latest_signal:
        blockers.append({"reason": "missing_signal", "detail": "No signal.csv available"})

    actionable_rows = [] if blockers else [{**instruction, "actionable": True}]
    pd.DataFrame(actionable_rows).to_csv(existing_actionable, index=False)

    pd.DataFrame([{**instruction, "watch_status": "monitor_next_signal"}]).to_csv(existing_watch, index=False)

    market_metadata = {
        "commodity_id": config.commodity_id,
        "fut_code": config.fut_code,
        "refresh_market_requested": refresh_market,
        "cache_dir": f"data/cache/{config.commodity_id}",
        "latest_signal_available": bool(latest_signal),
        "execution_blocker_count": len(blockers),
        "tushare_refresh": tushare_metadata,
    }
    write_json(metadata_dir / "market_data_metadata.json", market_metadata)
    write_json(metadata_dir / "execution_blockers.json", blockers)

    return {
        "latest_instruction": str(existing_instruction),
        "latest_actionable_trade": str(existing_actionable),
        "next_signal_watch": str(existing_watch),
        "market_data_metadata": str(metadata_dir / "market_data_metadata.json"),
        "execution_blockers": blockers,
        "actionable": not blockers,
    }
