from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    @staticmethod
    def success(data: dict[str, Any] | None = None) -> "ToolResult":
        return ToolResult(ok=True, data=data or {})

    @staticmethod
    def failure(code: str, message: str, details: dict[str, Any] | None = None) -> "ToolResult":
        return ToolResult(ok=False, error={"code": code, "message": message, "details": details or {}})
