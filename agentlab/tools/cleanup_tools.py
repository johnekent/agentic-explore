from __future__ import annotations

from pathlib import Path

from agentlab.pipeline.cleanup import cleanup_db_records
from agentlab.tools.types import ToolResult


def cleanup_db(workspace: str, dry_run: bool = True) -> ToolResult:
    try:
        report = cleanup_db_records(Path(workspace), dry_run=dry_run)
        return ToolResult.success(report)
    except Exception as exc:
        return ToolResult.failure("cleanup_error", str(exc))
