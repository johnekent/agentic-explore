from __future__ import annotations

import json
from typing import Any

from agentlab.providers.llm import get_provider

SYSTEM_SUMMARIZE = """You are a careful research assistant.
Extract a concise document title and summary from the provided content.
Return strict JSON:
{
  "title": "string",
  "summary": "string"
}
Title: 4-12 words, no quotes, no trailing punctuation.
Summary: 1-3 sentences, factual, 50-120 words.
"""


def summarize_document(text: str, *, url: str | None = None) -> dict[str, str]:
    llm = get_provider()
    prompt = text[:6000]
    if url:
        prompt = f"URL: {url}\n\nCONTENT:\n{prompt}"
    out = llm.complete(SYSTEM_SUMMARIZE, prompt).text
    if out.strip().startswith("(heuristic mode)"):
        raise RuntimeError("LLM not configured. Set AGENTLAB_LLM=ollama for summarization.")
    try:
        data = json.loads(out)
        title = str(data.get("title") or "").strip()
        summary = str(data.get("summary") or "").strip()
        if title or summary:
            return {"title": title, "summary": summary}
    except Exception:
        pass
    raise ValueError(f"Invalid summary JSON: {out[:200]}")
