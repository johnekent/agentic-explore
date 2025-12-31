from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from agentlab.skills_runtime.base import Skill, SkillSpec


@dataclass
class CaptureIdea(Skill):
    spec = SkillSpec(name="capture_idea", required_capabilities=["cap.persistence"])

    def run(self, orch, **kwargs) -> Dict[str, Any]:
        rows = kwargs.get("rows", [])
        result = orch.use("cap.persistence", table="ideas", rows=rows)
        if not result.ok:
            return {"ok": False, "error": result.error}
        return {"ok": True, "inserted": result.data.get("inserted", 0)}
