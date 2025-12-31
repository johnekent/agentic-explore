from __future__ import annotations

from pathlib import Path

from agentlab.pipeline.dedup import delete_documents, find_duplicate_groups
from agentlab.tools.types import ToolResult


def list_document_duplicates(db_path: str) -> ToolResult:
    try:
        groups = find_duplicate_groups(Path(db_path))
        return ToolResult.success({"groups": groups})
    except Exception as exc:
        return ToolResult.failure("dedup_error", str(exc))


def delete_duplicate_documents(db_path: str, doc_ids: list[str], delete_files: bool = True) -> ToolResult:
    try:
        result = delete_documents(Path(db_path), doc_ids, delete_files=delete_files)
        return ToolResult.success(result)
    except Exception as exc:
        return ToolResult.failure("dedup_error", str(exc))
