from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from ..config import CommodityConfig
from ..llm import get_llm, invoke_llm_text
from ..paths import ProjectPaths
from ..tools.io import write_json
from .code_writer import build_experiment_code, build_experiment_code_with_llm, build_experiment_prompt, parse_llm_experiment_code
from .evaluator import evaluate_experiment
from .promotion import write_promotion_proposal


def run_sandbox_experiment(
    *,
    project_root: Path,
    config: CommodityConfig,
    state: dict[str, Any],
    experiment_type: str,
    experiment_name: str,
) -> dict[str, Any]:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{config.commodity_id}_{_safe_name(experiment_name)}"
    run_dir = project_root / "sandbox" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    input_state = _sanitize_state(state)
    write_json(run_dir / "input_state.json", input_state)
    code_source = "template_fallback"
    llm_error: str | None = None
    try:
        paths = ProjectPaths.discover(project_root)
        llm = get_llm(paths)
        if llm is not None:
            code = build_experiment_code_with_llm(
                llm=llm,
                experiment_type=experiment_type,
                experiment_name=experiment_name,
                state=input_state,
            )
            code_source = "llm_qwen_langchain"
        else:
            prompt = build_experiment_prompt(experiment_type=experiment_type, experiment_name=experiment_name, state=input_state)
            content = invoke_llm_text(prompt, paths)
            if content:
                code = parse_llm_experiment_code(content)
                code_source = "llm_qwen_http"
            else:
                code = build_experiment_code(experiment_type, experiment_name)
                llm_error = "llm_unavailable_or_http_call_failed"
    except Exception as exc:
        code = build_experiment_code(experiment_type, experiment_name)
        llm_error = str(exc)

    write_json(
        run_dir / "run_metadata.json",
        {
            "run_id": run_id,
            "commodity_id": config.commodity_id,
            "experiment_type": experiment_type,
            "experiment_name": experiment_name,
            "code_source": code_source,
            "llm_error": llm_error,
            "sandbox_only": True,
        },
    )
    experiment_path = run_dir / "experiment.py"
    experiment_path.write_text(code, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(experiment_path)],
        cwd=str(run_dir),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    (run_dir / "stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(proc.stderr, encoding="utf-8")
    evaluation = evaluate_experiment(run_dir, proc.returncode)
    proposal = write_promotion_proposal(run_dir, evaluation)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "exit_code": proc.returncode,
        "experiment_result": str(run_dir / "experiment_result.json"),
        "experiment_report": str(run_dir / "experiment_report.md"),
        "promotion_proposal": str(proposal),
        "recommend_promotion": evaluation.get("recommend_promotion", False),
    }


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)[:80] or "experiment"


def _sanitize_state(state: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(state, ensure_ascii=False, default=str)
    for forbidden in ["DASHSCOPE_API_KEY", "api_key", "TOKEN", "token"]:
        text = text.replace(forbidden, "[REDACTED]")
    return json.loads(text)
