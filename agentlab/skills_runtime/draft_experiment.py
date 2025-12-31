from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from agentlab.skills_runtime.base import Skill, SkillSpec


@dataclass
class DraftExperiment(Skill):
    spec = SkillSpec(name="draft_experiment", required_capabilities=["cap.llm_generate"])

    def run(self, orch, **kwargs) -> Dict[str, Any]:
        system = "Draft a short experiment plan. Return JSON {\"plan\": \"...\"}."
        user = kwargs.get("text", "")[:2000]
        result = orch.use("cap.llm_generate", system=system, user=user, temperature=0.2)
        if not result.ok:
            return {"ok": False, "error": result.error}
        return {"ok": True, "raw": result.data.get("text", "")}
