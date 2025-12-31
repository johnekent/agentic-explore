from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from agentlab.orchestrator.runtime import Orchestrator


@dataclass(frozen=True)
class SkillSpec:
    name: str
    required_capabilities: List[str]


class Skill:
    spec: SkillSpec

    def run(self, orch: Orchestrator, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
