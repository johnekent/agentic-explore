from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from agentlab.orchestrator.runtime import Orchestrator, default_orchestrator
from agentlab.skills_runtime.capture_idea import CaptureIdea


@dataclass
class PlannerOrchestrator:
    orch: Orchestrator

    def run_capture_idea(self, rows: list[dict[str, Any]]) -> Dict[str, Any]:
        skill = CaptureIdea()
        return skill.run(self.orch, rows=rows)


def build_planner() -> PlannerOrchestrator:
    return PlannerOrchestrator(orch=default_orchestrator())
