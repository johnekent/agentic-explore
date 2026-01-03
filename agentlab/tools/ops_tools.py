from __future__ import annotations

from typing import Any

from agentlab.core.logging import end_run, log_interaction, log_span, log_tool_call, start_run
from agentlab.core.paths import utc_now_iso
from agentlab.tools.types import ToolResult


def ops_log(
    action: str,
    *,
    agent_name: str | None = None,
    agent_type: str | None = None,
    purpose: str | None = None,
    parent_run_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    tool_name: str | None = None,
    skill_name: str | None = None,
    parameters: dict[str, Any] | None = None,
    result_summary: str | None = None,
    duration_ms: int | None = None,
    with_agent: str | None = None,
    interaction_type: str | None = None,
    details: dict[str, Any] | None = None,
    span_name: str | None = None,
    span_category: str | None = None,
    span_status: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    metadata: dict[str, Any] | None = None,
    parent_span_id: str | None = None,
) -> ToolResult:
    try:
        if action == "start":
            if not agent_name or not agent_type or not purpose:
                return ToolResult.failure("invalid_args", "agent_name, agent_type, and purpose required.")
            new_run_id = start_run(agent_name, agent_type, purpose=purpose, parent_run_id=parent_run_id)
            return ToolResult.success({"run_id": new_run_id})
        if action == "end":
            if not run_id or not status:
                return ToolResult.failure("invalid_args", "run_id and status required.")
            end_run(run_id, status=status)
            return ToolResult.success({"run_id": run_id})
        if action == "tool_call":
            if not run_id or not tool_name:
                return ToolResult.failure("invalid_args", "run_id and tool_name required.")
            log_tool_call(
                run_id,
                tool_name,
                skill_name=skill_name,
                parameters=parameters,
                result_summary=result_summary,
                duration_ms=duration_ms,
            )
            return ToolResult.success({"run_id": run_id})
        if action == "interaction":
            if not run_id or not interaction_type:
                return ToolResult.failure("invalid_args", "run_id and interaction_type required.")
            log_interaction(
                run_id,
                with_agent or "status",
                interaction_type,
                details=details or {},
            )
            return ToolResult.success({"run_id": run_id})
        if action == "span":
            if not run_id or not span_name or duration_ms is None:
                return ToolResult.failure("invalid_args", "run_id, span_name, and duration_ms required.")
            log_span(
                run_id,
                span_name,
                skill_name=skill_name,
                category=span_category,
                status=span_status or "ok",
                duration_ms=duration_ms,
                started_at=started_at or utc_now_iso(),
                ended_at=ended_at or utc_now_iso(),
                metadata=metadata,
                parent_span_id=parent_span_id,
            )
            return ToolResult.success({"run_id": run_id, "span_name": span_name})
        return ToolResult.failure("invalid_action", f"Unknown action: {action}")
    except Exception as exc:
        return ToolResult.failure("ops_log_error", str(exc))
