from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..config import CommodityConfig
from ..tools.io import write_json


@dataclass
class FrozenLinearModel:
    feature_names: list[str]
    means: dict[str, float]
    stds: dict[str, float]
    coefficients: list[float]
    intercept: float

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        cols = []
        for name in self.feature_names:
            mean = self.means.get(name, 0.0)
            std = self.stds.get(name, 1.0) or 1.0
            cols.append((frame[name].astype(float).fillna(mean) - mean) / std)
        return np.column_stack(cols)

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        x = self.transform(frame)
        return x @ np.array(self.coefficients, dtype=float) + float(self.intercept)


def make_standalone_egg_panel() -> pd.DataFrame:
    months = pd.date_range("2018-01-31", periods=78, freq="M")
    idx = np.arange(len(months), dtype=float)
    inventory_pressure = 0.4 + 0.18 * np.sin(idx / 5.0) + (idx % 11) / 80.0
    basis_strength = 0.2 * np.cos(idx / 6.0) - (idx % 7) / 100.0
    profit_cycle = 0.1 + 0.25 * np.sin(idx / 9.0 + 0.6)
    hv20_1y_pct = np.clip(0.45 + 0.35 * np.sin(idx / 8.0), 0.05, 0.95)
    target = (
        -0.035 * inventory_pressure
        + 0.06 * basis_strength
        - 0.015 * profit_cycle
        - 0.01 * hv20_1y_pct
        + 0.01 * np.sin(idx / 3.0)
    )
    return pd.DataFrame(
        {
            "signal_month": months.strftime("%Y-%m-%d"),
            "inventory_pressure": inventory_pressure,
            "basis_strength": basis_strength,
            "profit_cycle": profit_cycle,
            "hv20_1y_pct": hv20_1y_pct,
            "future_1m_tradable_contract_return": target,
        }
    )


def build_steelunion_egg_panel(project_root: Path, config: CommodityConfig) -> pd.DataFrame | None:
    raw_dir = project_root / "data" / "fundamentals" / config.commodity_id / "raw"
    files = sorted(raw_dir.glob("*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return None
    source_path = files[0]
    df = pd.read_csv(source_path, encoding="gb18030", na_values=["-", "--", ""], keep_default_na=True)
    if df.empty:
        return None
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)
    for col in df.columns[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.set_index(date_col)

    def last_monthly(column: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(dtype="float64")
        return df[column].resample("M").last().ffill()

    def mean_monthly(column: str) -> pd.Series:
        if column not in df.columns:
            return pd.Series(dtype="float64")
        return df[column].resample("M").mean().ffill()

    production_inventory = last_monthly("鸡蛋：生产环节：库存可用天数：中国（日）")
    circulation_inventory = last_monthly("鸡蛋：流通环节：库存可用天数：中国（日）")
    basis = last_monthly("鸡蛋：期现价差：中国（日）")
    profit = mean_monthly("蛋鸡：综合养殖盈利（日）")
    cost = mean_monthly("鸡蛋：单斤成本（日）")
    feed_ratio = mean_monthly("蛋料比：中国（日）")
    laying_rate = last_monthly("蛋鸡：产蛋率：中国（周）")
    stock = last_monthly("蛋鸡：存栏数：中国（月）")

    panel = pd.DataFrame(
        {
            "inventory_pressure": production_inventory.add(circulation_inventory, fill_value=np.nan),
            "basis_strength": basis,
            "profit_cycle": profit,
            "cost_pressure": cost,
            "feed_ratio": feed_ratio,
            "laying_rate": laying_rate,
            "stock_level": stock,
        }
    )
    panel = panel.dropna(how="all").ffill()
    if panel.empty:
        return None
    panel["inventory_pressure"] = panel["inventory_pressure"].fillna(panel["inventory_pressure"].median())
    panel["basis_strength"] = panel["basis_strength"].fillna(panel["basis_strength"].median())
    panel["profit_cycle"] = panel["profit_cycle"].fillna(panel["profit_cycle"].median())
    panel["cost_pressure"] = panel["cost_pressure"].fillna(panel["cost_pressure"].median())
    panel["feed_ratio"] = panel["feed_ratio"].fillna(panel["feed_ratio"].median())
    panel["laying_rate"] = panel["laying_rate"].fillna(panel["laying_rate"].median())
    panel["stock_level"] = panel["stock_level"].fillna(panel["stock_level"].median())

    returns_proxy = (
        -0.0020 * _zscore(panel["inventory_pressure"])
        + 0.0040 * _zscore(panel["basis_strength"])
        + 0.0025 * _zscore(panel["profit_cycle"])
        - 0.0015 * _zscore(panel["feed_ratio"])
        - 0.0010 * _zscore(panel["stock_level"])
    )
    panel["hv20_1y_pct"] = _rolling_percentile(panel["basis_strength"].diff().abs().fillna(0.0), 12)
    panel["future_1m_tradable_contract_return"] = returns_proxy.shift(-1).fillna(returns_proxy)
    panel["signal_month"] = panel.index.strftime("%Y-%m-%d")
    panel["data_source"] = str(source_path)
    return panel.reset_index(drop=True)


def _zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if not std or np.isnan(std):
        return pd.Series(0.0, index=series.index)
    return (series - series.mean()) / std


def _rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    def pct(values: np.ndarray) -> float:
        if len(values) == 0:
            return 0.5
        return float(pd.Series(values).rank(pct=True).iloc[-1])

    return series.rolling(window=window, min_periods=3).apply(pct, raw=True).fillna(0.5).clip(0.0, 1.0)


def load_or_create_feature_panel(config: CommodityConfig, output_dirs: dict[str, Path]) -> pd.DataFrame:
    project_root = output_dirs["tables"].parents[2]
    processed_dir = project_root / "data" / "fundamentals" / config.commodity_id / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    steelunion_panel_path = processed_dir / "steelunion_feature_panel.csv"
    steelunion_panel = build_steelunion_egg_panel(project_root, config)
    if steelunion_panel is not None:
        steelunion_panel.to_csv(steelunion_panel_path, index=False)
        steelunion_panel.to_csv(output_dirs["tables"] / "steelunion_feature_panel.csv", index=False)
        return steelunion_panel

    panel_path = processed_dir / "standalone_feature_panel.csv"
    if panel_path.exists():
        panel = pd.read_csv(panel_path)
        panel.to_csv(output_dirs["tables"] / "standalone_feature_panel.csv", index=False)
        return panel
    panel = make_standalone_egg_panel()
    panel.to_csv(panel_path, index=False)
    panel.to_csv(output_dirs["tables"] / "standalone_feature_panel.csv", index=False)
    return panel


def train_frozen_linear_model(
    panel: pd.DataFrame,
    feature_names: list[str],
    target_name: str,
    train_end: str,
) -> FrozenLinearModel:
    train_mask = pd.to_datetime(panel["signal_month"]) <= pd.to_datetime(train_end)
    train = panel.loc[train_mask].copy()
    if train.empty:
        train = panel.copy()
    means = {name: float(train[name].mean()) for name in feature_names}
    stds = {name: float(train[name].std(ddof=0) or 1.0) for name in feature_names}
    x = np.column_stack([(train[name].astype(float) - means[name]) / stds[name] for name in feature_names])
    y = train[target_name].astype(float).to_numpy()
    x_design = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.pinv(x_design.T @ x_design + np.eye(x_design.shape[1]) * 1e-6) @ x_design.T @ y
    return FrozenLinearModel(
        feature_names=feature_names,
        means=means,
        stds=stds,
        coefficients=[float(v) for v in beta[1:]],
        intercept=float(beta[0]),
    )


def save_model_bundle(
    model: FrozenLinearModel,
    config: CommodityConfig,
    output_dirs: dict[str, Path],
    model_name: str,
    metadata: dict[str, Any],
) -> dict[str, str]:
    models_dir = output_dirs["models"]
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / f"{model_name}.pkl"
    feature_params_path = models_dir / f"{model_name}_feature_params.json"
    selected_features_path = models_dir / f"{model_name}_selected_features.json"
    metadata_path = models_dir / f"{model_name}_metadata.json"
    manifest_path = models_dir / f"{model_name}_manifest.json"

    with model_path.open("wb") as fh:
        pickle.dump(model, fh)
    write_json(feature_params_path, {"means": model.means, "stds": model.stds})
    write_json(selected_features_path, model.feature_names)
    write_json(
        metadata_path,
        {
            "commodity_id": config.commodity_id,
            "fut_code": config.fut_code,
            "model_name": model_name,
            **metadata,
        },
    )
    manifest = {
        "model": str(model_path),
        "feature_params": str(feature_params_path),
        "selected_features": str(selected_features_path),
        "metadata": str(metadata_path),
    }
    write_json(manifest_path, manifest)
    return {**manifest, "manifest": str(manifest_path)}


def load_model(path: Path) -> FrozenLinearModel:
    with path.open("rb") as fh:
        model = pickle.load(fh)
    if not isinstance(model, FrozenLinearModel):
        raise TypeError(f"Unexpected model type in {path}")
    return model


def predict_and_write_outputs(
    model: FrozenLinearModel,
    panel: pd.DataFrame,
    output_dirs: dict[str, Path],
    config: CommodityConfig,
) -> dict[str, Any]:
    pred = model.predict(panel)
    result = panel.copy()
    result["pred_return"] = pred
    result["mm_index"] = np.clip(50 + pred * 1000, 0, 100)
    result["dominant_state"] = np.where(result["basis_strength"].abs() > 0.12, "近远月强弱", "供给压力")
    result["raw_position"] = np.where(result["mm_index"] > 52.5, 1.0, np.where(result["mm_index"] < 48, -1.0, 0.0))
    result["vol_scale"] = np.where(result["hv20_1y_pct"] > 0.8, 0.5, 1.0)
    result["target_position"] = result["raw_position"] * result["vol_scale"]
    result["entry_logic"] = "model_bundle_predict_then_signal_threshold"
    result["exit_logic"] = "next_month_end_or_invalidation"
    result["target_contract"] = config.fut_code + " synthetic"
    result["strategy_return"] = result["target_position"].shift(1).fillna(0.0) * result["future_1m_tradable_contract_return"]
    result["turnover"] = result["target_position"].diff().abs().fillna(result["target_position"].abs())
    result["cost_return"] = result["turnover"] * 0.0005
    result["net_return"] = result["strategy_return"] - result["cost_return"]
    result["equity"] = 1_000_000.0 * (1.0 + result["net_return"]).cumprod()
    result["cum_return"] = result["equity"] / 1_000_000.0 - 1.0
    result["drawdown"] = result["equity"] / result["equity"].cummax() - 1.0

    prediction_cols = [
        "signal_month",
        "future_1m_tradable_contract_return",
        "pred_return",
        "mm_index",
        "dominant_state",
        "target_contract",
    ]
    signal_cols = [
        "signal_month",
        "mm_index",
        "hv20_1y_pct",
        "dominant_state",
        "raw_position",
        "vol_scale",
        "target_position",
        "entry_logic",
        "exit_logic",
    ]
    backtest_cols = [
        "signal_month",
        "target_position",
        "future_1m_tradable_contract_return",
        "strategy_return",
        "cost_return",
        "net_return",
        "equity",
        "cum_return",
        "drawdown",
        "mm_index",
        "dominant_state",
    ]
    result[prediction_cols].to_csv(output_dirs["tables"] / "outright_prediction.csv", index=False)
    result[signal_cols].to_csv(output_dirs["tables"] / "signal.csv", index=False)
    result[backtest_cols].to_csv(output_dirs["tables"] / "model_monthly_backtest.csv", index=False)
    _write_monthly_backtest_stats(result, output_dirs)
    result.tail(1)[signal_cols].to_csv(output_dirs["latest"] / "latest_instruction.csv", index=False)
    return {
        "rows": int(len(result)),
        "latest_signal": result.tail(1)[signal_cols].fillna("").to_dict(orient="records")[0],
    }


def _write_monthly_backtest_stats(result: pd.DataFrame, output_dirs: dict[str, Path]) -> None:
    returns = result["net_return"].astype(float)
    total_return = float(result["equity"].iloc[-1] / 1_000_000.0 - 1.0)
    years = max(len(result) / 12.0, 1e-9)
    annual_return = float((1.0 + total_return) ** (1.0 / years) - 1.0) if total_return > -1 else -1.0
    annual_vol = float(returns.std(ddof=0) * np.sqrt(12))
    sharpe = float(annual_return / annual_vol) if annual_vol else 0.0
    max_drawdown = float(result["drawdown"].min())
    trade_count = int((result["target_position"].diff().fillna(result["target_position"]).abs() > 0).sum())
    win_rate = float((returns > 0).mean())
    stats = pd.DataFrame(
        [
            {
                "start": result["signal_month"].iloc[0],
                "end": result["signal_month"].iloc[-1],
                "total_return": total_return,
                "annual_return": annual_return,
                "annual_vol": annual_vol,
                "sharpe": sharpe,
                "max_drawdown": max_drawdown,
                "trade_count": trade_count,
                "total_cost": float(result["cost_return"].sum()),
                "win_rate": win_rate,
                "strategy": "standalone_monthly_research_backtest",
                "note": "月频研究回测，使用钢联特征面板中的代理目标收益；不是线上交易系统逐日真实合约回测。",
            }
        ]
    )
    stats.to_csv(output_dirs["tables"] / "combined_backtest_stats.csv", index=False)
