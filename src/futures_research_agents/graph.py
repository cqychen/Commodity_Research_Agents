from __future__ import annotations

from pathlib import Path
from typing import Callable

from .config import CommodityConfig
from .nodes.core import (
    WorkflowContext,
    backtest_report_agent,
    calendar_model_agent,
    data_dictionary_agent,
    deliverables_agent,
    feature_study_agent,
    hypothesis_agent,
    latest_trade_execution_agent,
    leakage_audit_agent,
    load_existing_outputs_agent,
    outright_model_agent,
    project_intake,
    publish_agent,
    report_and_acceptance_agent,
    sandbox_model_experiment_agent,
    signal_synthesis_agent,
    target_builder_agent,
)
from .state import ResearchState


Node = Callable[[ResearchState, WorkflowContext], ResearchState]


RESEARCH_ONLY_NODES: list[Node] = [
    project_intake,
    hypothesis_agent,
    data_dictionary_agent,
    feature_study_agent,
    target_builder_agent,
    leakage_audit_agent,
    signal_synthesis_agent,
    latest_trade_execution_agent,
    backtest_report_agent,
    report_and_acceptance_agent,
    publish_agent,
    deliverables_agent,
]

EXPLAIN_EXISTING_NODES: list[Node] = [
    project_intake,
    load_existing_outputs_agent,
    hypothesis_agent,
    data_dictionary_agent,
    feature_study_agent,
    target_builder_agent,
    sandbox_model_experiment_agent,
    outright_model_agent,
    calendar_model_agent,
    leakage_audit_agent,
    signal_synthesis_agent,
    latest_trade_execution_agent,
    backtest_report_agent,
    report_and_acceptance_agent,
    publish_agent,
    deliverables_agent,
]

FULL_NODES: list[Node] = [
    project_intake,
    hypothesis_agent,
    data_dictionary_agent,
    feature_study_agent,
    target_builder_agent,
    sandbox_model_experiment_agent,
    outright_model_agent,
    calendar_model_agent,
    leakage_audit_agent,
    signal_synthesis_agent,
    latest_trade_execution_agent,
    backtest_report_agent,
    report_and_acceptance_agent,
    publish_agent,
    deliverables_agent,
]

LATEST_TRADE_NODES: list[Node] = [
    project_intake,
    load_existing_outputs_agent,
    signal_synthesis_agent,
    latest_trade_execution_agent,
    publish_agent,
    deliverables_agent,
]


def nodes_for_mode(mode: str) -> list[Node]:
    if mode == "research-only":
        return RESEARCH_ONLY_NODES
    if mode == "latest-trade":
        return LATEST_TRADE_NODES
    if mode == "full":
        return FULL_NODES
    return EXPLAIN_EXISTING_NODES


def run_workflow(
    *,
    config: CommodityConfig,
    output_dirs: dict[str, Path],
    docs_root: Path,
    mode: str,
    refresh_market: bool = False,
) -> ResearchState:
    prompts_root = output_dirs["latest"].parents[2] / "src" / "futures_research_agents" / "prompts"
    ctx = WorkflowContext(config=config, output_dirs=output_dirs, docs_root=docs_root, prompts_root=prompts_root)
    state: ResearchState = {
        "commodity_id": config.commodity_id,
        "mode": mode,  # type: ignore[typeddict-item]
        "refresh_market": refresh_market,
        "project_root": str(output_dirs["latest"].parents[2]),
    }
    for node in nodes_for_mode(mode):
        state = node(state, ctx)
    return state


def build_langgraph_app(
    *,
    config: CommodityConfig,
    output_dirs: dict[str, Path],
    docs_root: Path,
    mode: str,
):
    """Build a real LangGraph app when the optional dependency is installed."""
    try:
        from langgraph.graph import END, StateGraph
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("Install the optional 'agent' dependencies to use LangGraph runtime.") from exc

    prompts_root = output_dirs["latest"].parents[2] / "src" / "futures_research_agents" / "prompts"
    ctx = WorkflowContext(config=config, output_dirs=output_dirs, docs_root=docs_root, prompts_root=prompts_root)
    graph = StateGraph(ResearchState)
    selected_nodes = nodes_for_mode(mode)

    def wrap(node: Node):
        def _runner(state: ResearchState) -> ResearchState:
            return node(state, ctx)

        return _runner

    previous_name: str | None = None
    for node in selected_nodes:
        name = node.__name__
        graph.add_node(name, wrap(node))
        if previous_name is None:
            graph.set_entry_point(name)
        else:
            graph.add_edge(previous_name, name)
        previous_name = name
    if previous_name:
        graph.add_edge(previous_name, END)
    return graph.compile()
