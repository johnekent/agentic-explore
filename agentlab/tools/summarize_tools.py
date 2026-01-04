from __future__ import annotations

import json

from agentlab.providers.llm import get_provider
from agentlab.pipeline.summarize import SYSTEM_SUMMARIZE
from agentlab.tools.types import ToolResult


def _parse_summary_json(text: str) -> dict[str, str]:
    if not text.strip():
        raise ValueError("Empty summary payload.")
    data = json.loads(text)
    title = str(data.get("title") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if title or summary:
        return {"title": title, "summary": summary}
    raise ValueError("Empty summary payload.")


def _heuristic_title_summary(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = ""
    for line in lines[:5]:
        title = line.lstrip("#").strip()
        if title:
            break
    collapsed = " ".join(lines)
    summary = collapsed[:400].strip()
    return {"title": title, "summary": summary}


def summarize_document(
    text: str,
    *,
    url: str | None = None,
    prefer_chunking: bool = False,
    temperature: float = 0.2,
) -> ToolResult:
    try:
        prompt = text[:6000]
        if url:
            prompt = f"URL: {url}\n\nCONTENT:\n{prompt}"
        llm = get_provider()
        if prefer_chunking and len(text) > 2000:
            chunk_size = 900
            chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
            summaries: list[str] = []
            for chunk in chunks[:8]:
                chunk_prompt = f"Chunk:\n\n{chunk[:chunk_size]}"
                result = llm.complete(SYSTEM_SUMMARIZE, chunk_prompt, temperature=temperature)
                try:
                    parsed = _parse_summary_json(result.text)
                    summaries.append(parsed.get("summary") or "")
                except Exception:
                    summaries.append(_heuristic_title_summary(chunk).get("summary") or "")
            joined = " ".join([s for s in summaries if s])
            reduce_prompt = f"Summaries:\n{joined[:2000]}"
            reduce_res = llm.complete(SYSTEM_SUMMARIZE, reduce_prompt, temperature=temperature)
            try:
                return ToolResult.success(_parse_summary_json(reduce_res.text))
            except Exception:
                return ToolResult.success(_heuristic_title_summary(joined or text))
        result = llm.complete(SYSTEM_SUMMARIZE, prompt, temperature=temperature)
        return ToolResult.success(_parse_summary_json(result.text))
    except Exception:
        return ToolResult.success(_heuristic_title_summary(text))
