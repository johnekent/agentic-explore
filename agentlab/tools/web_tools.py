from __future__ import annotations

import requests
from agentlab.pipeline.web import ddg_html_search
from agentlab.tools.types import ToolResult


def search_web(query: str, top_n: int = 10) -> ToolResult:
    try:
        hits = ddg_html_search(query, top_n=top_n)
        return ToolResult.success({"results": [h.__dict__ for h in hits]})
    except Exception as exc:
        return ToolResult.failure("search_error", str(exc))


def fetch_url(url: str, timeout_s: int = 30, headers: dict[str, str] | None = None) -> ToolResult:
    try:
        req_headers = headers or {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=req_headers, timeout=timeout_s)
        r.raise_for_status()
        return ToolResult.success({"status": r.status_code, "text": r.text})
    except Exception as exc:
        return ToolResult.failure("fetch_error", str(exc))
