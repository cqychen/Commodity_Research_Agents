from __future__ import annotations

import importlib
import os
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import CommodityConfig
from ..tools.io import write_json


def load_tushare_token(project_root: Path) -> tuple[str | None, str]:
    env_token = os.environ.get("TUSHARE_TOKEN")
    if env_token:
        return env_token, "env:TUSHARE_TOKEN"
    candidates = [
        project_root / "config" / "tushare.config",
        project_root / "configs" / "tushare.config",
        project_root.parent / "线上预测" / "鸡蛋" / "config" / "tushare.config",
        project_root.parent / "鸡蛋" / "light_rf_calendar_v3_trading_system" / "config" / "tushare.config",
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        match = re.search(r"TOKEN\s*=\s*['\"]([^'\"]+)['\"]", text)
        if match:
            return match.group(1), str(path)
    return None, "missing"


def refresh_tushare_cache(
    *,
    project_root: Path,
    config: CommodityConfig,
    output_dirs: dict[str, Path],
    start_date: str = "20190101",
    sleep_seconds: float = 0.12,
) -> dict[str, Any]:
    cache_dir = project_root / "data" / "cache" / config.commodity_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dirs["metadata"] / "tushare_refresh_metadata.json"
    token, token_source = load_tushare_token(project_root)
    metadata: dict[str, Any] = {
        "commodity_id": config.commodity_id,
        "fut_code": config.fut_code,
        "token_source": token_source,
        "success": False,
        "cache_dir": str(cache_dir),
    }
    if not token:
        metadata["error"] = "未找到 Tushare token。请设置 TUSHARE_TOKEN 或创建 config/tushare.config。"
        write_json(metadata_path, metadata)
        return metadata
    try:
        ts = importlib.import_module("tushare")
        pro = ts.pro_api(token)
        contracts = pro.fut_basic(
            exchange="",
            fut_type="",
            ts_code="",
            fut_code=config.fut_code,
            fields="ts_code,symbol,exchange,name,list_date,delist_date,d_month",
        )
        if contracts is None or contracts.empty:
            raise RuntimeError("Tushare fut_basic 未返回合约。")
        contracts = contracts[contracts["d_month"].notna()].copy()
        contracts["list_date"] = pd.to_datetime(contracts["list_date"], format="%Y%m%d", errors="coerce")
        contracts["delist_date"] = pd.to_datetime(contracts["delist_date"], format="%Y%m%d", errors="coerce")
        contracts["delivery_month"] = pd.to_datetime(contracts["d_month"].astype(int).astype(str), format="%Y%m", errors="coerce")
        contracts = contracts.dropna(subset=["list_date", "delist_date", "delivery_month"])
        start_ts = pd.to_datetime(start_date)
        end_ts = pd.Timestamp.today().normalize()
        target = contracts[(contracts["list_date"] <= end_ts) & (contracts["delist_date"] >= start_ts)].copy()
        frames: list[pd.DataFrame] = []
        for _, row in target.sort_values(["delivery_month", "ts_code"]).iterrows():
            daily = pro.fut_daily(
                ts_code=row["ts_code"],
                start_date=max(row["list_date"], start_ts).strftime("%Y%m%d"),
                end_date=min(row["delist_date"], end_ts).strftime("%Y%m%d"),
            )
            if daily is None or daily.empty:
                time.sleep(sleep_seconds)
                continue
            daily["trade_date"] = pd.to_datetime(daily["trade_date"], format="%Y%m%d", errors="coerce")
            daily["active_contract"] = row["ts_code"]
            daily["list_date"] = row["list_date"]
            daily["delist_date"] = row["delist_date"]
            daily["delivery_month"] = row["delivery_month"]
            daily["continuous_price"] = daily.get("close", daily.get("settle"))
            frames.append(daily)
            time.sleep(sleep_seconds)
        if not frames:
            raise RuntimeError("Tushare fut_daily 未返回日线。")
        all_daily = pd.concat(frames, ignore_index=True).sort_values(["trade_date", "delivery_month", "active_contract"])
        all_daily_path = cache_dir / f"{config.fut_code}_all_contract_daily.csv"
        all_daily.to_csv(all_daily_path, index=False)
        continuous = _build_continuous(all_daily)
        continuous_path = cache_dir / f"{config.fut_code}_continuous.csv"
        continuous.to_csv(continuous_path, index=False)
        metadata.update(
            {
                "success": True,
                "all_contract_daily": str(all_daily_path),
                "continuous": str(continuous_path),
                "contracts": int(contracts.shape[0]),
                "daily_rows": int(all_daily.shape[0]),
                "max_trade_date": str(all_daily["trade_date"].max().date()),
            }
        )
    except Exception as exc:
        metadata["error"] = f"{type(exc).__name__}: {exc}"
    write_json(metadata_path, metadata)
    return metadata


def _build_continuous(all_daily: pd.DataFrame) -> pd.DataFrame:
    df = all_daily.dropna(subset=["trade_date", "delivery_month", "continuous_price"]).copy()
    df["months_to_delivery"] = (
        (df["delivery_month"].dt.year - df["trade_date"].dt.year) * 12
        + (df["delivery_month"].dt.month - df["trade_date"].dt.month)
    )
    df = df[df["months_to_delivery"] > 0].sort_values(["trade_date", "delivery_month", "active_contract"])
    if df.empty:
        return pd.DataFrame()
    return df.groupby("trade_date", as_index=False).first()
