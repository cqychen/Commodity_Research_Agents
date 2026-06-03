from __future__ import annotations

import argparse
import sys

from .config import load_commodity_config
from .graph import run_workflow
from .llm import load_llm_config
from .paths import ProjectPaths
from .sandbox.runner import run_sandbox_experiment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run single commodity futures research agents")
    parser.add_argument("--commodity", default="egg", help="Commodity config id, e.g. egg")
    parser.add_argument(
        "--mode",
        default="explain-existing",
        choices=["research-only", "explain-existing", "latest-trade", "full", "sandbox-feature", "sandbox-model"],
        help="Workflow mode",
    )
    parser.add_argument("--experiment-name", default="default_experiment", help="Sandbox experiment name")
    parser.add_argument("--refresh-market", action="store_true", help="Record a market refresh request for latest trade mode")
    parser.add_argument("--print-summary", action="store_true", help="Print a concise run summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = ProjectPaths.discover()
    config = load_commodity_config(args.commodity, paths)
    output_dirs = paths.ensure_output_dirs(config.commodity_id)

    # Load once to validate config and key location without exposing the key.
    load_llm_config(paths)

    mode = args.mode
    workflow_mode = "full" if mode in {"sandbox-feature", "sandbox-model"} else mode
    state = run_workflow(
        config=config,
        output_dirs=output_dirs,
        docs_root=paths.docs_root,
        mode=workflow_mode,
        refresh_market=args.refresh_market,
    )
    if mode in {"sandbox-feature", "sandbox-model"}:
        experiment_type = "feature_experiment" if mode == "sandbox-feature" else "model_experiment"
        sandbox_result = run_sandbox_experiment(
            project_root=paths.project_root,
            config=config,
            state=state,
            experiment_type=experiment_type,
            experiment_name=args.experiment_name,
        )
        state["sandbox_result"] = sandbox_result  # type: ignore[typeddict-unknown-key]

    if args.print_summary:
        print(f"commodity={state.get('commodity_id')}")
        print(f"mode={mode}")
        print(f"reports={state.get('report_paths', {})}")
        if state.get("sandbox_result"):
            print(f"sandbox={state.get('sandbox_result')}")
        print(f"deliverables={len(state.get('deliverables_manifest', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
