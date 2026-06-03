from __future__ import annotations

from pathlib import Path

from futures_research_agents.config import load_commodity_config
from futures_research_agents.graph import run_workflow
from futures_research_agents.paths import ProjectPaths
from futures_research_agents.sandbox.runner import run_sandbox_experiment


def test_explain_existing_smoke() -> None:
    paths = ProjectPaths.discover(Path(__file__).resolve())
    config = load_commodity_config("egg", paths)
    output_dirs = paths.ensure_output_dirs("egg")
    state = run_workflow(
        config=config,
        output_dirs=output_dirs,
        docs_root=paths.docs_root,
        mode="explain-existing",
        refresh_market=False,
    )

    assert state["commodity_id"] == "egg"
    assert (output_dirs["latest"] / "latest_instruction.csv").exists()
    assert (output_dirs["reports"] / "research_report.md").exists()
    assert (output_dirs["reports"] / "commodity_scorecard.md").exists()
    assert (output_dirs["metadata"] / "run_metadata.json").exists()


def test_full_workflow_persists_models() -> None:
    paths = ProjectPaths.discover(Path(__file__).resolve())
    config = load_commodity_config("egg", paths)
    output_dirs = paths.ensure_output_dirs("egg")
    state = run_workflow(
        config=config,
        output_dirs=output_dirs,
        docs_root=paths.docs_root,
        mode="full",
        refresh_market=False,
    )

    assert state["mode"] == "full"
    assert (output_dirs["models"] / "outright_model.pkl").exists()
    assert (output_dirs["models"] / "outright_model_manifest.json").exists()
    assert (output_dirs["models"] / "calendar_model.pkl").exists()
    assert (output_dirs["models"] / "calendar_model_manifest.json").exists()
    assert (output_dirs["tables"] / "signal.csv").exists()
    assert (output_dirs["latest"] / "latest_instruction.csv").exists()


def test_sandbox_feature_experiment() -> None:
    paths = ProjectPaths.discover(Path(__file__).resolve())
    config = load_commodity_config("egg", paths)
    output_dirs = paths.ensure_output_dirs("egg")
    state = run_workflow(
        config=config,
        output_dirs=output_dirs,
        docs_root=paths.docs_root,
        mode="full",
        refresh_market=False,
    )
    result = run_sandbox_experiment(
        project_root=paths.project_root,
        config=config,
        state=state,
        experiment_type="feature_experiment",
        experiment_name="smoke_feature_test",
    )
    run_dir = Path(result["run_dir"])
    assert (run_dir / "experiment.py").exists()
    assert (run_dir / "experiment_result.json").exists()
    assert (run_dir / "experiment_report.md").exists()
    assert (run_dir / "promotion_proposal.md").exists()


if __name__ == "__main__":
    test_explain_existing_smoke()
    test_full_workflow_persists_models()
    test_sandbox_feature_experiment()
