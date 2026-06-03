from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .paths import ProjectPaths


@dataclass(frozen=True)
class CommodityConfig:
    commodity_id: str
    display_name: str
    fut_code: str
    exchange: str
    prefix: str
    existing_system_path: Path | None
    contract_multiplier: float
    commission_per_hand: float
    slippage_per_hand: float
    min_entry_volume: float
    min_entry_oi: float
    delist_buffer_days: int
    train_end: str
    valid_end: str
    calendar_states: tuple[str, ...]
    raw: dict[str, Any]


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_commodity_config(commodity_id: str, paths: ProjectPaths | None = None) -> CommodityConfig:
    paths = paths or ProjectPaths.discover()
    config_path = paths.configs_root / "commodities" / f"{commodity_id}.yaml"
    data = load_yaml(config_path)
    existing_value = data.get("existing_system_path")
    existing = Path(existing_value) if existing_value else None
    if existing is not None and not existing.is_absolute():
        existing = (paths.project_root / existing).resolve()
    return CommodityConfig(
        commodity_id=str(data["commodity_id"]),
        display_name=str(data["display_name"]),
        fut_code=str(data["fut_code"]),
        exchange=str(data["exchange"]),
        prefix=str(data.get("prefix", data["commodity_id"])),
        existing_system_path=existing,
        contract_multiplier=float(data.get("contract_multiplier", 1.0)),
        commission_per_hand=float(data.get("commission_per_hand", 0.0)),
        slippage_per_hand=float(data.get("slippage_per_hand", 0.0)),
        min_entry_volume=float(data.get("min_entry_volume", 0.0)),
        min_entry_oi=float(data.get("min_entry_oi", 0.0)),
        delist_buffer_days=int(data.get("delist_buffer_days", 0)),
        train_end=str(data.get("train_end", "")),
        valid_end=str(data.get("valid_end", "")),
        calendar_states=tuple(data.get("calendar_states", [])),
        raw=data,
    )
