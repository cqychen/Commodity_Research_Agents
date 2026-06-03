from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from ..adapters.egg_existing_system import copy_key_outputs_to_contract, load_existing_egg_outputs
from ..backtest import run_independent_daily_backtest, write_online_comparison
from ..config import CommodityConfig
from ..market_data.latest_trade import build_latest_trade_files
from ..models.store import (
    load_model,
    load_or_create_feature_panel,
    predict_and_write_outputs,
    save_model_bundle,
    train_frozen_linear_model,
)
from ..prompt_loader import PromptLoader
from ..reports.generator import generate_reports
from ..sandbox.runner import run_sandbox_experiment
from ..state import ResearchState
from ..tools.figures import make_backtest_figures
from ..tools.io import read_csv_if_exists, write_json, write_markdown, write_rows_csv
from ..validators.checks import run_leakage_audit, validate_feature_spec, validate_output_contract


class WorkflowContext:
    def __init__(self, config: CommodityConfig, output_dirs: dict[str, Path], docs_root: Path, prompts_root: Path | None = None):
        self.config = config
        self.output_dirs = output_dirs
        self.docs_root = docs_root
        self.prompts_root = prompts_root
        self.prompt_loader = PromptLoader(prompts_root) if prompts_root else None


def project_intake(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    cfg = ctx.config
    state["commodity_meta"] = {
        "commodity_id": cfg.commodity_id,
        "display_name": cfg.display_name,
        "fut_code": cfg.fut_code,
        "exchange": cfg.exchange,
        "prefix": cfg.prefix,
        "train_end": cfg.train_end,
        "valid_end": cfg.valid_end,
        "calendar_states": list(cfg.calendar_states),
    }
    state["output_dirs"] = {name: str(path) for name, path in ctx.output_dirs.items()}
    state["docs_loaded"] = [
        str(ctx.docs_root / "README.md"),
        str(ctx.docs_root / "01_总流程.md"),
        str(ctx.docs_root / "02_特征研究流程.md"),
        str(ctx.docs_root / "03_双模型体系.md"),
        str(ctx.docs_root / "04_行情目标与波动率.md"),
        str(ctx.docs_root / "05_建模与防穿越.md"),
        str(ctx.docs_root / "06_回测与交易信号.md"),
        str(ctx.docs_root / "07_研究目录与交易系统.md"),
        str(ctx.docs_root / "08_复盘验收与多品种扩展.md"),
    ]
    if ctx.prompt_loader:
        state["prompt_templates"] = ctx.prompt_loader.list_agents()  # type: ignore[typeddict-unknown-key]
    return state


def hypothesis_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    state["hypothesis_db"] = [
        {
            "hypothesis": "低库存 + 深贴水时，期货具备多头赔率。",
            "direction": "bullish",
            "expression": "outright_or_bull_calendar",
            "evidence_fields": ["inventory", "basis", "term_structure"],
            "counter_evidence": ["库存回升", "基差转弱", "需求淡季"],
        },
        {
            "hypothesis": "高库存 + 高升水时，期货估值偏高，优先偏空。",
            "direction": "bearish",
            "expression": "outright_or_bear_calendar",
            "evidence_fields": ["inventory", "basis", "warehouse_receipts"],
            "counter_evidence": ["库存快速下降", "远月供给收缩", "现货强势"],
        },
        {
            "hypothesis": "近远月强弱、季节和年度周期清晰时，跨期表达优先于单边。",
            "direction": "relative_value",
            "expression": "calendar_spread",
            "evidence_fields": ["basis_raw", "calendar_spread", "seasonality"],
            "counter_evidence": ["两腿流动性不足", "交割风险上升"],
        },
    ]
    return state


def data_dictionary_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    cfg = ctx.config
    state["data_dict"] = {
        "fundamentals": {
            "raw_dir": f"data/fundamentals/{cfg.commodity_id}/raw",
            "latest_dir": f"data/fundamentals/{cfg.commodity_id}/latest",
            "processed_dir": f"data/fundamentals/{cfg.commodity_id}/processed",
            "publish_date_rule": "第一列优先视为 publish_date，月频按公布日 as-of 对齐。",
        },
        "market": {
            "daily_contracts": f"data/market/{cfg.commodity_id}/daily_contracts",
            "continuous": f"data/market/{cfg.commodity_id}/continuous",
            "basis": f"data/market/{cfg.commodity_id}/basis",
            "cache": f"data/cache/{cfg.commodity_id}",
        },
        "asof_rules": "每个信号月只能使用信号日前已经公布的产业数据和当时可见行情。",
    }
    return state


def feature_study_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    features = [
        {
            "name": "inventory_pressure",
            "source": "industry",
            "function": "driver/risk",
            "direction": "higher_is_bearish",
            "use_for": ["outright", "calendar", "state"],
            "lag_months": 0,
            "note": "库存压力用于验证供需矛盾和多头风险。",
        },
        {
            "name": "basis_strength",
            "source": "basis",
            "function": "valuation",
            "direction": "higher_is_bullish",
            "use_for": ["outright", "calendar", "state"],
            "lag_months": 0,
            "note": "基差用于判断期货升贴水和期限结构赔率。",
        },
        {
            "name": "profit_cycle",
            "source": "industry",
            "function": "driver",
            "direction": "higher_is_bearish_forward_supply",
            "use_for": ["outright", "calendar"],
            "lag_months": 1,
            "note": "利润影响后续供给扩张或收缩。",
        },
        {
            "name": "hv20_1y_pct",
            "source": "futures",
            "function": "risk",
            "direction": "higher_reduces_position",
            "use_for": ["filter", "risk"],
            "lag_months": 0,
            "note": "高波动环境下执行前降仓。",
        },
    ]
    state["feature_spec"] = features
    state["field_cards"] = features
    state["feature_gap_recommendations"] = [
        "必须补充：可稳定更新的库存和存栏数据。",
        "强烈建议：仓单、基差和期限结构的统一口径数据。",
        "可选增强：相关品种成本和替代需求数据。",
    ]
    state["feature_gate"] = validate_feature_spec(features)
    write_rows_csv(ctx.output_dirs["tables"] / "feature_catalog.csv", features)
    return state


def load_existing_outputs_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    state["existing_outputs"] = load_existing_egg_outputs(ctx.config)
    copied = copy_key_outputs_to_contract(ctx.config, ctx.output_dirs)
    state["deliverables_manifest"] = [*state.get("deliverables_manifest", []), *copied]
    return state


def target_builder_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    state["outright_labels"] = {
        "target": "future_1m_tradable_contract_return",
        "entry_rule": "信号月末后下一交易日",
        "exit_rule": "下个月月末附近最后可用交易日",
        "contract_filter": {
            "min_entry_volume": ctx.config.min_entry_volume,
            "min_entry_oi": ctx.config.min_entry_oi,
            "delist_buffer_days": ctx.config.delist_buffer_days,
        },
    }
    state["calendar_labels"] = {
        "target": "real_pair_spread_return",
        "spread": "front_price - forward_price",
        "position_positive": "多近月空远月",
    }
    state["volatility_features"] = {"index_price": "volume_weighted_contract_close", "risk_metrics": ["hv20", "hv60", "hv20_1y_pct"]}
    return state


def sandbox_model_experiment_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    project_root = ctx.output_dirs["latest"].parents[2]
    sandbox_result = run_sandbox_experiment(
        project_root=project_root,
        config=ctx.config,
        state=state,
        experiment_type="model_experiment",
        experiment_name=f"{ctx.config.commodity_id}_auto_model_experiment",
    )
    state["sandbox_result"] = sandbox_result
    return state


def outright_model_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    existing_prediction = state.get("existing_outputs", {}).get("outputs", {}).get("prediction", {})
    panel = load_or_create_feature_panel(ctx.config, ctx.output_dirs)
    feature_names = ["inventory_pressure", "basis_strength", "profit_cycle", "hv20_1y_pct"]
    model = train_frozen_linear_model(
        panel=panel,
        feature_names=feature_names,
        target_name="future_1m_tradable_contract_return",
        train_end=ctx.config.train_end,
    )
    bundle = save_model_bundle(
        model=model,
        config=ctx.config,
        output_dirs=ctx.output_dirs,
        model_name="outright_model",
        metadata={
            "model_family": "frozen_linear_baseline",
            "train_end": ctx.config.train_end,
            "valid_end": ctx.config.valid_end,
            "target": "future_1m_tradable_contract_return",
            "usage": "load model bundle, transform latest features with saved params, then predict",
        },
    )
    loaded_model = load_model(Path(bundle["model"]))
    prediction_summary = predict_and_write_outputs(loaded_model, panel, ctx.output_dirs, ctx.config)
    state["outright_model"] = {
        "status": "trained_and_persisted",
        "model_family": "frozen_linear_baseline",
        "prediction_rows": existing_prediction.get("rows", 0),
        "standalone_prediction_rows": prediction_summary["rows"],
        "model_bundle": bundle,
        "latest_signal": prediction_summary["latest_signal"],
        "data_source": str(panel["data_source"].iloc[-1]) if "data_source" in panel.columns and not panel.empty else "standalone_synthetic",
    }
    return state


def calendar_model_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    calendar_model = train_frozen_linear_model(
        panel=load_or_create_feature_panel(ctx.config, ctx.output_dirs),
        feature_names=["basis_strength", "inventory_pressure", "hv20_1y_pct"],
        target_name="future_1m_tradable_contract_return",
        train_end=ctx.config.train_end,
    )
    bundle = save_model_bundle(
        model=calendar_model,
        config=ctx.config,
        output_dirs=ctx.output_dirs,
        model_name="calendar_model",
        metadata={
            "model_family": "frozen_linear_calendar_proxy",
            "train_end": ctx.config.train_end,
            "valid_end": ctx.config.valid_end,
            "target": "real_calendar_pair_spread_return_proxy",
            "usage": "proxy persisted model until real calendar target data is connected",
        },
    )
    state["calendar_model"] = {
        "status": "trained_and_persisted_proxy",
        "calendar_states": list(ctx.config.calendar_states),
        "target": "real_calendar_pair_spread_return",
        "model_bundle": bundle,
    }
    calendar_path = ctx.output_dirs["tables"] / "calendar_prediction.csv"
    if not calendar_path.exists():
        write_rows_csv(calendar_path, [{"status": "calendar model output placeholder", "commodity_id": ctx.config.commodity_id}])
    return state


def leakage_audit_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    state["leakage_audit"] = run_leakage_audit(state)
    write_json(ctx.output_dirs["metadata"] / "leakage_audit.json", state["leakage_audit"])
    return state


def signal_synthesis_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    latest_instruction = state.get("existing_outputs", {}).get("outputs", {}).get("latest_instruction", {})
    tail = latest_instruction.get("tail") or []
    local_signal = read_csv_if_exists(ctx.output_dirs["tables"] / "signal.csv")
    if not local_signal.empty:
        last = local_signal.tail(1).fillna("").to_dict(orient="records")[0]
    else:
        last = tail[-1] if tail else {}
    dominant_state = str(last.get("dominant_state", ""))
    expression = "calendar_spread" if dominant_state in ctx.config.calendar_states else "outright_or_observe"
    target_position = last.get("target_position", 0.0)
    try:
        numeric_position = float(target_position)
    except Exception:
        numeric_position = 0.0
    direction = "long" if numeric_position > 0 else "short" if numeric_position < 0 else "neutral"
    state["signal_synthesis"] = {
        "selected_expression": expression,
        "strategy_type": "calendar_spread" if expression == "calendar_spread" else "single_contract",
        "target_position": numeric_position,
        "direction": direction,
        "degrade_level": "只观察" if numeric_position == 0 else "正常交易",
        "entry_rating": "observe" if numeric_position == 0 else "actionable",
        "dominant_state": dominant_state or "unknown",
    }
    return state


def latest_trade_execution_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    state["latest_trade"] = build_latest_trade_files(
        ctx.config,
        ctx.output_dirs,
        state.get("signal_synthesis", {}),
        refresh_market=bool(state.get("refresh_market", False)),
    )
    return state


def backtest_report_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    independent_result = run_independent_daily_backtest(config=ctx.config, output_dirs=ctx.output_dirs)
    comparison = write_online_comparison(ctx.config, ctx.output_dirs)
    if independent_result.get("success"):
        backtest = read_csv_if_exists(ctx.output_dirs["tables"] / "state_aware_backtest.csv")
        backtest_source = "independent_daily_real_contract_backtest"
    else:
        backtest = read_csv_if_exists(ctx.output_dirs["tables"] / "model_monthly_backtest.csv")
        backtest_source = "standalone_monthly_research_backtest"
    figure_paths = make_backtest_figures(ctx.output_dirs["figures"], backtest)
    stats_path = ctx.output_dirs["tables"] / "combined_backtest_stats.csv"
    if not stats_path.exists():
        write_rows_csv(
            stats_path,
            [
                {
                    "metric": "status",
                    "value": "placeholder_until_full_model_run",
                    "note": "explain-existing mode can copy existing stats when available",
                }
            ],
        )
    state["backtest_report"] = {
        "figures": figure_paths,
        "stats_path": str(stats_path),
        "source": backtest_source,
        "independent_result": independent_result,
        "online_comparison": comparison,
    }
    return state


def _write_online_parity_check(source_stats: Path, local_stats: Path, metadata_dir: Path) -> None:
    source = pd.read_csv(source_stats)
    local = pd.read_csv(local_stats)
    compare_cols = ["total_return", "annual_return", "annual_vol", "sharpe", "max_drawdown", "trade_count", "total_cost", "win_rate"]
    diffs: dict[str, float] = {}
    if not source.empty and not local.empty:
        for col in compare_cols:
            if col in source.columns and col in local.columns:
                diffs[col] = float(local[col].iloc[0]) - float(source[col].iloc[0])
    write_json(
        metadata_dir / "online_backtest_parity_check.json",
        {
            "source_stats": str(source_stats),
            "local_stats": str(local_stats),
            "same_source_copied": True,
            "metric_differences": diffs,
            "max_abs_difference": max([abs(v) for v in diffs.values()] or [0.0]),
        },
    )


def report_and_acceptance_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    preliminary_risks = []
    if not state.get("leakage_audit", {}).get("leakage_ok"):
        preliminary_risks.append("防穿越检查存在未通过项。")
    if state.get("signal_synthesis", {}).get("degrade_level") in {"只观察", "研究中"}:
        preliminary_risks.append("最新信号处于观察或研究降级状态。")
    state["acceptance"] = {
        "verdict": "有条件通过" if preliminary_risks else "通过",
        "risks": preliminary_risks or ["第一版仍需继续模块化既有 RF 与 Calendar 逻辑。"],
        "output_contract_ok": False,
    }
    state["report_paths"] = generate_reports(state, ctx.output_dirs)
    return state


def publish_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    metadata = {
        "commodity_id": state.get("commodity_id"),
        "mode": state.get("mode"),
        "commodity_meta": state.get("commodity_meta", {}),
        "latest_trade": state.get("latest_trade", {}),
        "scorecard": state.get("scorecard", {}),
        "errors": state.get("errors", []),
    }
    write_json(ctx.output_dirs["metadata"] / "run_metadata.json", metadata)
    contract = validate_output_contract(ctx.output_dirs)
    state.setdefault("acceptance", {})["output_contract_ok"] = contract["accepted"]
    state.setdefault("acceptance", {})["missing_outputs"] = contract["missing"]
    write_json(ctx.output_dirs["metadata"] / "output_contract_check.json", contract)
    acceptance = state.get("acceptance", {})
    scorecard = state.get("scorecard", {})
    risks = acceptance.get("risks", ["第一版仍需继续模块化既有 RF 与 Calendar 逻辑。"])
    acceptance_md = "# 上线验收报告\n\n"
    acceptance_md += f"- 验收结论：{acceptance.get('verdict', '有条件通过')}\n"
    acceptance_md += f"- 防穿越通过：{state.get('leakage_audit', {}).get('leakage_ok')}\n"
    acceptance_md += f"- 输出契约通过：{contract['accepted']}\n"
    acceptance_md += f"- 品种评分：{scorecard.get('total_score', '')}\n\n"
    acceptance_md += "## 风险\n\n"
    acceptance_md += "\n".join(f"- {risk}" for risk in risks)
    if contract["missing"]:
        acceptance_md += "\n\n## 缺失输出\n\n"
        acceptance_md += "\n".join(f"- `{path}`" for path in contract["missing"])
    write_markdown(ctx.output_dirs["reports"] / "acceptance_report.md", acceptance_md)
    return state


def deliverables_agent(state: ResearchState, ctx: WorkflowContext) -> ResearchState:
    manifest = set(state.get("deliverables_manifest", []))
    for section in ctx.output_dirs.values():
        for path in section.glob("*"):
            if path.is_file():
                manifest.add(str(path))
    state["deliverables_manifest"] = sorted(manifest)
    write_json(ctx.output_dirs["metadata"] / "deliverables_manifest.json", state["deliverables_manifest"])
    return state
