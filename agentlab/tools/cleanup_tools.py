from __future__ import annotations

from pathlib import Path

from agentlab.pipeline.cleanup import cleanup_db_records, delete_all_data_records, cleanup_unreferenced_content
from agentlab.tools.types import ToolResult


def cleanup_db(workspace: str, dry_run: bool = True) -> ToolResult:
    try:
        report = cleanup_db_records(Path(workspace), dry_run=dry_run)
        return ToolResult.success(report)
    except Exception as exc:
        return ToolResult.failure("cleanup_error", str(exc))


def delete_all_data(workspace: str, delete_files: bool = True) -> ToolResult:
    try:
        report = delete_all_data_records(Path(workspace), delete_files=delete_files)
        return ToolResult.success(report)
    except Exception as exc:
        return ToolResult.failure("cleanup_error", str(exc))


def cleanup_content(workspace: str, dry_run: bool = True) -> ToolResult:
    try:
        report = cleanup_unreferenced_content(Path(workspace), dry_run=dry_run)
        return ToolResult.success(report)
    except Exception as exc:
        return ToolResult.failure("cleanup_error", str(exc))
