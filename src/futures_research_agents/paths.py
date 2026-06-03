from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    data_root: Path
    output_root: Path
    configs_root: Path
    docs_root: Path
    prompts_root: Path
    sandbox_root: Path

    @classmethod
    def discover(cls, start: Path | None = None) -> "ProjectPaths":
        root = (start or Path(__file__).resolve()).resolve()
        for parent in [root, *root.parents]:
            if (parent / "pyproject.toml").exists() and (parent / "configs").exists():
                project_root = parent
                break
        else:
            project_root = Path.cwd()

        return cls(
            project_root=project_root,
            data_root=project_root / "data",
            output_root=project_root / "output",
            configs_root=project_root / "configs",
            docs_root=project_root.parent / "公用文档" / "单品种期货研究流程",
            prompts_root=project_root / "src" / "futures_research_agents" / "prompts",
            sandbox_root=project_root / "sandbox",
        )

    def commodity_output(self, commodity_id: str) -> Path:
        return self.output_root / commodity_id

    def ensure_output_dirs(self, commodity_id: str) -> dict[str, Path]:
        base = self.commodity_output(commodity_id)
        dirs = {
            "latest": base / "latest",
            "tables": base / "tables",
            "figures": base / "figures",
            "reports": base / "reports",
            "metadata": base / "metadata",
            "models": base / "models",
        }
        for path in dirs.values():
            path.mkdir(parents=True, exist_ok=True)
        return dirs
