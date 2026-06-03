from __future__ import annotations

from typing import Any, Literal, TypedDict


RunMode = Literal["research-only", "explain-existing", "latest-trade", "full", "sandbox-feature", "sandbox-model"]


class ResearchState(TypedDict, total=False):
    commodity_id: str
    mode: RunMode
    refresh_market: bool
    project_root: str
    output_dirs: dict[str, str]
    commodity_meta: dict[str, Any]
    docs_loaded: list[str]
    hypothesis_db: list[dict[str, Any]]
    data_dict: dict[str, Any]
    field_cards: list[dict[str, Any]]
    feature_spec: list[dict[str, Any]]
    feature_gate: dict[str, Any]
    existing_outputs: dict[str, Any]
    outright_labels: dict[str, Any]
    calendar_labels: dict[str, Any]
    volatility_features: dict[str, Any]
    outright_model: dict[str, Any]
    calendar_model: dict[str, Any]
    leakage_audit: dict[str, Any]
    signal_synthesis: dict[str, Any]
    latest_trade: dict[str, Any]
    backtest_report: dict[str, Any]
    scorecard: dict[str, Any]
    report_paths: dict[str, str]
    acceptance: dict[str, Any]
    prompt_templates: list[str]
    sandbox_result: dict[str, Any]
    deliverables_manifest: list[str]
    errors: list[str]


def add_error(state: ResearchState, message: str) -> ResearchState:
    state.setdefault("errors", []).append(message)
    return state
