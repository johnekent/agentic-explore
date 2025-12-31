from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import yaml


@dataclass(frozen=True)
class Capability:
    id: str
    description: str
    default_tool: str


def load_capabilities(path: Path = Path("capabilities.yaml")) -> Dict[str, Capability]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    caps = {}
    for entry in data.get("capabilities", []):
        cid = str(entry.get("id") or "").strip()
        if not cid:
            continue
        caps[cid] = Capability(
            id=cid,
            description=str(entry.get("description") or ""),
            default_tool=str(entry.get("default_tool") or ""),
        )
    return caps
