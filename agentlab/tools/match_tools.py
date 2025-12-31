from __future__ import annotations

from pathlib import Path

from agentlab.core.config import get_setting
from agentlab.pipeline.matching import match_doc_to_ideas as _match_doc_to_ideas
from agentlab.pipeline.matching import match_idea_to_docs as _match_idea_to_docs
from agentlab.tools.types import ToolResult


def _db_path(db_path: str | None = None) -> Path:
    return Path(db_path) if db_path else Path(get_setting("AGENTLAB_DB_PATH", "workspace/index/agent.db"))


def match_idea_to_docs(idea_id: str, top_n: int = 10, db_path: str | None = None) -> ToolResult:
    try:
        results = _match_idea_to_docs(_db_path(db_path), idea_id, top_n=top_n)
        payload = [r.__dict__ for r in results]
        return ToolResult.success({"matches": payload})
    except Exception as exc:
        return ToolResult.failure("match_error", str(exc))


def match_doc_to_ideas(document_id: str, top_n: int = 10, db_path: str | None = None) -> ToolResult:
    try:
        results = _match_doc_to_ideas(_db_path(db_path), document_id, top_n=top_n)
        payload = [r.__dict__ for r in results]
        return ToolResult.success({"matches": payload})
    except Exception as exc:
        return ToolResult.failure("match_error", str(exc))
