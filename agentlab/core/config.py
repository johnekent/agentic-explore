from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import os
import yaml


CONFIG_PATH = Path("config.yaml")


@dataclass(frozen=True)
class AppConfig:
    llm_provider: str = ""
    ollama_model: str = ""
    ollama_base_url: str = ""
    db_path: str = ""


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    data = _read_yaml(path)
    llm = str(data.get("llm_provider") or "").strip()
    ollama = data.get("ollama") or {}
    if not isinstance(ollama, dict):
        ollama = {}
    db_path = str(data.get("db_path") or "").strip()
    return AppConfig(
        llm_provider=llm,
        ollama_model=str(ollama.get("model") or "").strip(),
        ollama_base_url=str(ollama.get("base_url") or "").strip(),
        db_path=db_path,
    )


def get_setting(name: str, default: str = "") -> str:
    env = os.getenv(name)
    if env:
        return env
    cfg = load_config()
    if name == "AGENTLAB_DB_PATH":
        return cfg.db_path or default
    if name == "AGENTLAB_LLM":
        return cfg.llm_provider or default
    if name == "OLLAMA_MODEL":
        return cfg.ollama_model or default
    if name == "OLLAMA_BASE_URL":
        return cfg.ollama_base_url or default
    return default
