from __future__ import annotations

import time
from typing import Any

from agentlab.orchestrator.runtime import Orchestrator
from agentlab.tools.types import ToolResult


def _require_ok(result: ToolResult, context: str) -> ToolResult:
    if not result.ok:
        if _should_ignore_ops_error(result, context):
            return result
        raise RuntimeError(f"{context}: {result.error}")
    return result


def _should_ignore_ops_error(result: ToolResult, context: str) -> bool:
    if context not in {"ops_end", "ops_tool_call"}:
        return False
    error = result.error or {}
    if error.get("code") != "ops_log_error":
        return False
    message = str(error.get("message", "")).lower()
    return "database is locked" in message or "foreign key constraint failed" in message


def start_ops_run(
    orch: Orchestrator,
    *,
    agent_name: str,
    agent_type: str,
    purpose: str,
    parent_run_id: str | None = None,
) -> str:
    result = orch.use(
        "cap.ops_logging",
        action="start",
        agent_name=agent_name,
        agent_type=agent_type,
        purpose=purpose,
        parent_run_id=parent_run_id,
    )
    _require_ok(result, "ops_start")
    return str(result.data.get("run_id"))


def end_ops_run(orch: Orchestrator, *, run_id: str, status: str) -> None:
    result = orch.use("cap.ops_logging", action="end", run_id=run_id, status=status)
    _require_ok(result, "ops_end")


def log_tool(
    orch: Orchestrator,
    *,
    run_id: str,
    tool_name: str,
    skill_name: str,
    parameters: dict[str, Any] | None = None,
    result_summary: str | None = None,
    duration_ms: int | None = None,
) -> None:
    result = orch.use(
        "cap.ops_logging",
        action="tool_call",
        run_id=run_id,
        tool_name=tool_name,
        skill_name=skill_name,
        parameters=parameters,
        result_summary=result_summary,
        duration_ms=duration_ms,
    )
    _require_ok(result, "ops_tool_call")


def use_tool(
    orch: Orchestrator,
    *,
    capability: str,
    run_id: str,
    skill_name: str,
    parameters: dict[str, Any] | None = None,
    **kwargs: Any,
) -> ToolResult:
    tool_name = orch.registry.capability_to_tool.get(capability, capability)
    start = time.time()
    result = orch.use(capability, **kwargs)
    duration_ms = int((time.time() - start) * 1000)
    summary = "ok" if result.ok else f"error:{result.error.get('code')}"
    log_tool(
        orch,
        run_id=run_id,
        tool_name=tool_name,
        skill_name=skill_name,
        parameters=parameters,
        result_summary=summary,
        duration_ms=duration_ms,
    )
    return result


def emit_status(
    orch: Orchestrator,
    *,
    run_id: str,
    skill_name: str,
    message: str,
    level: str = "info",
    stage: str | None = None,
    log_fn=None,
) -> None:
    details = {"message": message, "level": level}
    if stage:
        details["stage"] = stage
    orch.use(
        "cap.ops_logging",
        action="interaction",
        run_id=run_id,
        with_agent=skill_name,
        interaction_type="status",
        details=details,
    )
    if log_fn:
        log_fn(message)
