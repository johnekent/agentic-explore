from __future__ import annotations

from pathlib import Path

from agentlab.pipeline.planning import (
    assign_task_agent,
    get_task_backlog,
    plan_match_execution,
    update_task_status,
)
from agentlab.tools.types import ToolResult


def plan_match_execution_tool(workspace: str, match_id: str) -> ToolResult:
    try:
        task_id = plan_match_execution(Path(workspace), match_id)
        return ToolResult.success({"task_id": task_id})
    except Exception as exc:
        return ToolResult.failure("plan_error", str(exc))


def plan_backlog_tool(workspace: str) -> ToolResult:
    try:
        tasks = get_task_backlog(Path(workspace))
        return ToolResult.success({"tasks": [dict(t) for t in tasks]})
    except Exception as exc:
        return ToolResult.failure("plan_error", str(exc))


def plan_update_status_tool(workspace: str, task_id: str, status: str) -> ToolResult:
    try:
        update_task_status(Path(workspace), task_id, status)
        return ToolResult.success({"task_id": task_id, "status": status})
    except Exception as exc:
        return ToolResult.failure("plan_error", str(exc))


def plan_assign_agent_tool(workspace: str, task_id: str, agent: str) -> ToolResult:
    try:
        assign_task_agent(Path(workspace), task_id, agent)
        return ToolResult.success({"task_id": task_id, "agent": agent})
    except Exception as exc:
        return ToolResult.failure("plan_error", str(exc))
