from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def make_backtest_figures(figures_dir: Path, backtest: pd.DataFrame | None = None) -> list[str]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    if backtest is None or backtest.empty or not {"equity", "cum_return", "drawdown"}.issubset(backtest.columns):
        return _make_unavailable_figures(figures_dir)

    df = backtest.copy()
    date_col = "trade_date" if "trade_date" in df.columns else "signal_month" if "signal_month" in df.columns else ""
    if not date_col:
        return _make_unavailable_figures(figures_dir)
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).sort_values(date_col)
    if df.empty:
        return _make_unavailable_figures(figures_dir)
    is_online_daily = date_col == "trade_date"
    title_suffix = "线上同口径逐日真实合约回测" if is_online_daily else "研究模型月频回测"
    x_label = "交易日" if is_online_daily else "信号月份"

    equity_path = figures_dir / "equity_curve.png"
    plt.figure(figsize=(10, 5))
    plt.plot(df[date_col], df["equity"].astype(float))
    plt.title(f"权益曲线（{title_suffix}）")
    plt.xlabel(x_label)
    plt.ylabel("权益")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(equity_path)
    plt.close()
    paths.append(str(equity_path))

    drawdown_path = figures_dir / "drawdown_curve.png"
    plt.figure(figsize=(10, 5))
    plt.plot(df[date_col], df["drawdown"].astype(float))
    plt.title(f"回撤曲线（{title_suffix}）")
    plt.xlabel(x_label)
    plt.ylabel("回撤")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(drawdown_path)
    plt.close()
    paths.append(str(drawdown_path))

    split_path = figures_dir / "train_valid_test_backtest.png"
    plt.figure(figsize=(10, 5))
    plt.plot(df[date_col], df["cum_return"].astype(float))
    plt.axvline(pd.Timestamp("2021-12-31"), linestyle="--", color="gray", label="训练截止")
    plt.axvline(pd.Timestamp("2023-12-31"), linestyle="--", color="black", label="验证截止")
    plt.title(f"收益分段图（{title_suffix}）")
    plt.xlabel(x_label)
    plt.ylabel("累计收益")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(split_path)
    plt.close()
    paths.append(str(split_path))

    return paths


def _make_unavailable_figures(figures_dir: Path) -> list[str]:
    paths: list[str] = []
    for filename, title in [
        ("equity_curve.png", "权益曲线不可用"),
        ("drawdown_curve.png", "回撤曲线不可用"),
        ("train_valid_test_backtest.png", "分段回测不可用"),
    ]:
        path = figures_dir / filename
        plt.figure(figsize=(10, 5))
        plt.text(
            0.5,
            0.5,
            "未找到真实回测表，拒绝生成占位假曲线。\n请先生成包含 equity/cum_return/drawdown 的回测数据。",
            ha="center",
            va="center",
        )
        plt.axis("off")
        plt.title(title)
        plt.tight_layout()
        plt.savefig(path)
        plt.close()
        paths.append(str(path))
    return paths
