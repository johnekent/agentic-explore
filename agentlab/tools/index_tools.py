from __future__ import annotations

from pathlib import Path

from agentlab.core.config import get_setting
from agentlab.pipeline.indexing import upsert_document, upsert_idea
from agentlab.tools.types import ToolResult


def _db_path() -> Path:
    return Path(get_setting("AGENTLAB_DB_PATH", "workspace/index/agent.db"))


def index_document(doc_path: str) -> ToolResult:
    try:
        doc_id = upsert_document(_db_path(), Path(doc_path))
        return ToolResult.success({"id": doc_id, "path": doc_path})
    except Exception as exc:
        return ToolResult.failure("index_error", str(exc))


def index_idea(idea_path: str) -> ToolResult:
    try:
        idea_id = upsert_idea(_db_path(), Path(idea_path))
        return ToolResult.success({"id": idea_id, "path": idea_path})
    except Exception as exc:
        return ToolResult.failure("index_error", str(exc))
