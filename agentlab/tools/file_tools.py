from __future__ import annotations

from pathlib import Path
from agentlab.tools.types import ToolResult


def list_files(root: str, pattern: str = "**/*") -> ToolResult:
    try:
        base = Path(root)
        if not base.exists():
            return ToolResult.failure("not_found", "Root path does not exist.")
        files = [str(p) for p in base.glob(pattern) if p.is_file()]
        return ToolResult.success({"files": files})
    except Exception as exc:
        return ToolResult.failure("list_error", str(exc))


def read_file(path: str) -> ToolResult:
    try:
        p = Path(path)
        if not p.exists():
            return ToolResult.failure("not_found", "File does not exist.")
        return ToolResult.success({"content": p.read_text(encoding="utf-8")})
    except Exception as exc:
        return ToolResult.failure("read_error", str(exc))


def write_file(path: str, content: str) -> ToolResult:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult.success({"path": str(p)})
    except Exception as exc:
        return ToolResult.failure("write_error", str(exc))
