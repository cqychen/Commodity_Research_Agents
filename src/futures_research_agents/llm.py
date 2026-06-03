from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import load_yaml
from .paths import ProjectPaths


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    base_url: str
    temperature: float
    timeout_seconds: int
    api_key: str | None


def load_llm_config(paths: ProjectPaths | None = None) -> LLMConfig:
    paths = paths or ProjectPaths.discover()
    data = load_yaml(paths.configs_root / "llm.yaml")
    key = os.environ.get("DASHSCOPE_API_KEY")
    key_file = data.get("api_key_file")
    key_field = data.get("api_key_field", "DASHSCOPE_API_KEY")
    if not key and key_file:
        candidate = Path(str(key_file))
        if not candidate.is_absolute():
            candidate = (paths.configs_root / candidate).resolve()
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as fh:
                raw: dict[str, Any] = json.load(fh)
            value = raw.get(key_field)
            key = str(value) if value else None

    return LLMConfig(
        provider=str(data.get("provider", "dashscope_openai_compatible")),
        model=str(data.get("model", "qwen3.7")),
        base_url=str(data.get("base_url", "")),
        temperature=float(data.get("temperature", 0.2)),
        timeout_seconds=int(data.get("timeout_seconds", 60)),
        api_key=key,
    )


def get_llm(paths: ProjectPaths | None = None):
    """Return an optional chat model without logging or exposing the API key."""
    cfg = load_llm_config(paths)
    if not cfg.api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except Exception:
        return None
    return ChatOpenAI(
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.base_url or None,
        temperature=cfg.temperature,
        timeout=cfg.timeout_seconds,
    )


def invoke_llm_text(prompt: str, paths: ProjectPaths | None = None) -> str | None:
    """Call an OpenAI-compatible chat endpoint using stdlib only."""
    cfg = load_llm_config(paths)
    if not cfg.api_key or not cfg.base_url:
        return None
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": cfg.temperature,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=cfg.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    parsed = json.loads(raw)
    choices = parsed.get("choices", [])
    if not choices:
        return None
    message = choices[0].get("message", {})
    content = message.get("content")
    return str(content) if content else None
