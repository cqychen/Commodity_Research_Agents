from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import CommodityConfig
from .tools.io import write_json


def run_independent_daily_backtest(
    *,
    config: CommodityConfig,
    output_dirs: dict[str, Path],
    initial_capital: float = 1_000_000.0,
    leverage: float = 0.9,
) -> dict[str, Any]:
    project_root = output_dirs["tables"].parents[2]
    daily_path = project_root / "data" / "cache" / config.commodity_id / f"{config.fut_code}_all_contract_daily.csv"
    signal_path = output_dirs["tables"] / "signal.csv"
    if not daily_path.exists() or not signal_path.exists():
        return {"success": False, "reason": "missing_daily_or_signal", "daily_path": str(daily_path), "signal_path": str(signal_path)}

    daily = pd.read_csv(daily_path)
    signal = pd.read_csv(signal_path)
    if daily.empty or signal.empty:
        return {"success": False, "reason": "empty_daily_or_signal"}

    daily["trade_date"] = pd.to_datetime(daily["trade_date"], errors="coerce")
    daily["delivery_month"] = pd.to_datetime(daily["delivery_month"], errors="coerce")
    daily["delist_date"] = pd.to_datetime(daily["delist_date"], errors="coerce")
    daily["price"] = pd.to_numeric(daily.get("close", daily.get("continuous_price")), errors="coerce").fillna(
        pd.to_numeric(daily.get("settle"), errors="coerce")
    )
    daily["vol"] = pd.to_numeric(daily.get("vol"), errors="coerce").fillna(0.0)
    daily["oi"] = pd.to_numeric(daily.get("oi"), errors="coerce").fillna(0.0)
    daily = daily.dropna(subset=["trade_date", "delivery_month", "price"]).sort_values(["trade_date", "delivery_month"])

    signal["signal_month"] = pd.to_datetime(signal["signal_month"], errors="coerce")
    signal["target_position"] = pd.to_numeric(signal["target_position"], errors="coerce").fillna(0.0)
    signal = signal.dropna(subset=["signal_month"]).sort_values("signal_month")

    equity = float(initial_capital)
    records: list[dict[str, Any]] = []
    total_cost = 0.0
    previous_equity_peak = equity
    trade_count = 0

    for _, sig in signal.iterrows():
        position = float(sig["target_position"])
        if position == 0:
            continue
        signal_month = pd.Timestamp(sig["signal_month"])
        entry_candidates = daily[daily["trade_date"] > signal_month]
        if entry_candidates.empty:
            continue
        entry_date = entry_candidates["trade_date"].min()
        exit_cutoff = signal_month + pd.offsets.MonthEnd(1)
        window_dates = daily[(daily["trade_date"] >= entry_date) & (daily["trade_date"] <= exit_cutoff)]["trade_date"]
        if window_dates.empty:
            continue
        exit_date = window_dates.max()
        contract = _select_contract(daily, entry_date, exit_date, config)
        if not contract:
            continue
        contract_df = daily[
            (daily["active_contract"] == contract)
            & (daily["trade_date"] >= entry_date)
            & (daily["trade_date"] <= exit_date)
        ].sort_values("trade_date")
        if len(contract_df) < 2:
            continue
        entry_price = float(contract_df["price"].iloc[0])
        hands = int((equity * leverage * abs(position)) / (entry_price * config.contract_multiplier))
        if hands <= 0:
            continue
        hands *= 1 if position > 0 else -1
        entry_cost = abs(hands) * (config.commission_per_hand + config.slippage_per_hand)
        equity -= entry_cost
        total_cost += entry_cost
        trade_count += 1
        prev_price = entry_price
        for row_idx, row in contract_df.iterrows():
            price = float(row["price"])
            daily_pnl = 0.0 if row_idx == contract_df.index[0] else hands * config.contract_multiplier * (price - prev_price)
            trade_cost = entry_cost if row_idx == contract_df.index[0] else 0.0
            if row_idx == contract_df.index[-1]:
                exit_cost = abs(hands) * (config.commission_per_hand + config.slippage_per_hand)
                daily_pnl -= exit_cost
                trade_cost += exit_cost
                total_cost += exit_cost
            equity += daily_pnl
            previous_equity_peak = max(previous_equity_peak, equity)
            records.append(
                {
                    "trade_date": row["trade_date"],
                    "signal_month": signal_month,
                    "strategy_type": "single_contract",
                    "selected_expression": sig.get("dominant_state", ""),
                    "held_contract": contract,
                    "front_contract": "",
                    "forward_contract": "",
                    "target_position": position,
                    "effective_leverage": leverage,
                    "hands": hands,
                    "daily_pnl": daily_pnl,
                    "trade_cost": trade_cost,
                    "equity": equity,
                    "mm_index": sig.get("mm_index", np.nan),
                    "dominant_state": sig.get("dominant_state", ""),
                    "trade_direction": "long_single" if hands > 0 else "short_single",
                    "daily_return": daily_pnl / max(equity - daily_pnl, 1.0),
                    "cum_return": equity / initial_capital - 1.0,
                    "drawdown": equity / previous_equity_peak - 1.0,
                }
            )
            prev_price = price

    if not records:
        return {"success": False, "reason": "no_trades_generated"}
    backtest = pd.DataFrame(records)
    backtest.to_csv(output_dirs["tables"] / "state_aware_backtest.csv", index=False)
    event_count = trade_count * 2
    stats = _compute_stats(backtest, initial_capital, total_cost, event_count)
    stats.to_csv(output_dirs["tables"] / "combined_backtest_stats.csv", index=False)
    write_json(
        output_dirs["metadata"] / "independent_daily_backtest_metadata.json",
        {
            "success": True,
            "rows": int(len(backtest)),
            "round_trip_count": trade_count,
            "trade_event_count": event_count,
            "initial_capital": initial_capital,
            "effective_leverage": leverage,
            "signal_thresholds": {"long_mm_index_gt": 52.5, "short_mm_index_lt": 48.0},
            "copied_online_result": False,
        },
    )
    return {"success": True, "rows": int(len(backtest)), "trade_count": event_count, "stats": stats.iloc[0].to_dict()}


def _select_contract(daily: pd.DataFrame, entry_date: pd.Timestamp, exit_date: pd.Timestamp, config: CommodityConfig) -> str | None:
    day = daily[daily["trade_date"] == entry_date].copy()
    if day.empty:
        return None
    min_delist = exit_date + pd.Timedelta(days=config.delist_buffer_days)
    day = day[(day["delist_date"] >= min_delist) & (day["vol"] >= config.min_entry_volume) & (day["oi"] >= config.min_entry_oi)]
    day = day[day["delivery_month"] > entry_date].sort_values(["delivery_month", "active_contract"])
    if day.empty:
        return None
    return str(day.iloc[0]["active_contract"])


def _compute_stats(backtest: pd.DataFrame, initial_capital: float, total_cost: float, trade_count: int) -> pd.DataFrame:
    start = pd.to_datetime(backtest["trade_date"]).min()
    end = pd.to_datetime(backtest["trade_date"]).max()
    total_return = float(backtest["equity"].iloc[-1] / initial_capital - 1.0)
    years = max((end - start).days / 365.25, 1e-9)
    annual_return = float((1 + total_return) ** (1 / years) - 1) if total_return > -1 else -1.0
    daily_returns = pd.to_numeric(backtest["daily_return"], errors="coerce").fillna(0.0)
    annual_vol = float(daily_returns.std(ddof=0) * np.sqrt(252))
    sharpe = annual_return / annual_vol if annual_vol else 0.0
    max_drawdown = float(pd.to_numeric(backtest["drawdown"], errors="coerce").min())
    win_rate = float((daily_returns > 0).mean())
    return pd.DataFrame(
        [
            {
                "start": start.date(),
                "end": end.date(),
                "total_return": total_return,
                "annual_return": annual_return,
                "annual_vol": annual_vol,
                "sharpe": sharpe,
                "max_drawdown": max_drawdown,
                "trade_count": trade_count,
                "total_cost": total_cost,
                "win_rate": win_rate,
                "strategy": "independent_single_contract_daily_backtest",
            }
        ]
    )


def write_online_comparison(config: CommodityConfig, output_dirs: dict[str, Path]) -> dict[str, Any]:
    if config.existing_system_path is None:
        return {"available": False, "reason": "missing_online_reference"}
    source_stats = config.existing_system_path / "output" / "egg_backtest_stats.csv"
    local_stats = output_dirs["tables"] / "combined_backtest_stats.csv"
    if not source_stats.exists() or not local_stats.exists():
        return {"available": False, "reason": "missing_stats"}
    source = pd.read_csv(source_stats)
    local = pd.read_csv(local_stats)
    cols = ["total_return", "annual_return", "annual_vol", "sharpe", "max_drawdown", "trade_count", "total_cost", "win_rate"]
    diffs = {}
    for col in cols:
        if col in source.columns and col in local.columns and not source.empty and not local.empty:
            diffs[col] = float(local[col].iloc[0]) - float(source[col].iloc[0])
    result = {
        "available": True,
        "source_stats": str(source_stats),
        "local_stats": str(local_stats),
        "copied_online_result": False,
        "metric_differences": diffs,
        "max_abs_difference": max([abs(v) for v in diffs.values()] or [0.0]),
    }
    write_json(output_dirs["metadata"] / "online_backtest_parity_check.json", result)
    return result
