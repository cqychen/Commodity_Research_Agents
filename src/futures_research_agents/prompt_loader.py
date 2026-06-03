from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class PromptLoader:
    def __init__(self, prompts_dir: Path):
        self.prompts_dir = prompts_dir

    def load(self, agent_name: str) -> str:
        path = self.prompts_dir / f"{agent_name}.md"
        if not path.exists():
            raise FileNotFoundError(f"缺少 Prompt 模板: {path}")
        return path.read_text(encoding="utf-8")

    def render(self, agent_name: str, *, state: dict[str, Any], config: Any, docs_summary: str = "") -> str:
        template = self.load(agent_name)
        config_data = asdict(config) if is_dataclass(config) else config
        context = {
            "state": _json_preview(state),
            "config": _json_preview(config_data),
            "docs_summary": docs_summary,
        }
        return template + "\n\n# 当前上下文\n\n" + "\n\n".join(
            [f"## {key}\n\n```json\n{value}\n```" if key != "docs_summary" else f"## {key}\n\n{value}" for key, value in context.items()]
        )

    def list_agents(self) -> list[str]:
        return sorted(path.stem for path in self.prompts_dir.glob("*_agent.md"))


def _json_preview(value: Any, limit: int = 4000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if len(text) > limit:
        return text[:limit] + "\n..."
    return text
