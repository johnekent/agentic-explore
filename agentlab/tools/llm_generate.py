from __future__ import annotations

from agentlab.providers.llm import get_provider
from agentlab.tools.types import ToolResult


def llm_generate(system: str, user: str, temperature: float = 0.2) -> ToolResult:
    try:
        llm = get_provider()
        result = llm.complete(system, user, temperature=temperature)
        return ToolResult.success({"text": result.text, "raw": result.raw})
    except Exception as exc:
        return ToolResult.failure("llm_error", str(exc))
