from __future__ import annotations

from pathlib import Path

from agentlab.pipeline.judges import build_dashboard_md, judge_validity
from agentlab.tools.types import ToolResult


def judge_validity_tool(db_path: str) -> ToolResult:
    try:
        report = judge_validity(Path(db_path))
        return ToolResult.success({"report": report})
    except Exception as exc:
        return ToolResult.failure("judge_error", str(exc))


def build_dashboard_tool(db_path: str, output_path: str) -> ToolResult:
    try:
        build_dashboard_md(Path(db_path), Path(output_path))
        return ToolResult.success({"path": output_path})
    except Exception as exc:
        return ToolResult.failure("dashboard_error", str(exc))
