from __future__ import annotations

import json
from typing import Any

from agentlab.core.config import get_setting
from agentlab.skills_runtime.ops_helpers import emit_status, perf_span, use_tool


def parse_summary_json(text: str) -> dict[str, str]:
    if not text.strip():
        raise ValueError("Empty summary payload.")
    if text.strip().startswith("(heuristic mode)"):
        raise RuntimeError("LLM not configured. Set AGENTLAB_LLM=ollama for summarization.")
    data = json.loads(text)
    title = str(data.get("title") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if title or summary:
        return {"title": title, "summary": summary}
    raise ValueError("Empty summary payload.")


def heuristic_title_summary(text: str) -> dict[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = ""
    for line in lines[:5]:
        title = line.lstrip("#").strip()
        if title:
            break
    collapsed = " ".join(lines)
    summary = collapsed[:400].strip()
    return {"title": title, "summary": summary}


def summarize_with_fallback(
    orch,
    *,
    run_id: str,
    skill_name: str,
    system: str,
    prompt: str,
    text: str,
    doc_id: str | None = None,
    prefer_chunking: bool = False,
    log_fn=None,
) -> dict[str, str]:
    span_meta = {"doc_id": doc_id, "prefer_chunking": prefer_chunking, "text_len": len(text)}
    with perf_span(
        orch,
        run_id=run_id,
        skill_name=skill_name,
        span_name="summarize_document",
        category="llm",
        metadata=span_meta,
    ):
        try:
            timeout_s = int(get_setting("OLLAMA_TIMEOUT_S", "300"))
        except ValueError:
            timeout_s = 300

        def compute_chunk_size(text_len: int) -> int:
            base = 600 if timeout_s <= 120 else 900 if timeout_s <= 300 else 1200
            return max(400, min(base, max(400, int(text_len * 0.2))))

        def _call_llm(user_prompt: str, retry_label: str | None = None):
            params = {"doc_id": doc_id} if doc_id else {}
            if retry_label:
                params["retry"] = retry_label
            return use_tool(
                orch,
                capability="cap.llm_generate",
                run_id=run_id,
                skill_name=skill_name,
                parameters=params,
                system=system,
                user=user_prompt,
                temperature=0.2,
            )

        llm_res = None
        if not prefer_chunking:
            llm_res = _call_llm(prompt)
            if not llm_res.ok and "timed out" in str(llm_res.error.get("message", "")).lower():
                short_prompt = prompt[:1200]
                llm_res = _call_llm(short_prompt, "short_prompt")
                if not llm_res.ok and "timed out" in str(llm_res.error.get("message", "")).lower():
                    tiny_prompt = prompt[:600]
                    llm_res = _call_llm(tiny_prompt, "tiny_prompt")

        if prefer_chunking or (llm_res is not None and not llm_res.ok):
            chunk_size = compute_chunk_size(len(text))
            if chunk_size < len(text):
                emit_status(
                    orch,
                    run_id=run_id,
                    skill_name=skill_name,
                    message=f"Summary chunking fallback size={chunk_size} chars",
                    level="warn",
                    stage="fallback",
                    log_fn=log_fn,
                )
                chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
                summaries: list[str] = []
                for idx, chunk in enumerate(chunks[:8], start=1):
                    chunk_prompt = f"Chunk {idx}/{min(len(chunks), 8)}:\n\n{chunk[:chunk_size]}"
                    chunk_res = _call_llm(chunk_prompt, f"chunk_{idx}")
                    if chunk_res.ok:
                        try:
                            parsed = parse_summary_json(str(chunk_res.data.get("text") or ""))
                            summaries.append(parsed.get("summary") or "")
                        except Exception:
                            summaries.append(heuristic_title_summary(chunk).get("summary") or "")
                    else:
                        summaries.append(heuristic_title_summary(chunk).get("summary") or "")
                joined = " ".join([s for s in summaries if s])
                reduce_prompt = f"Summaries:\n{joined[:2000]}"
                reduce_res = _call_llm(reduce_prompt, "reduce")
                if reduce_res.ok:
                    try:
                        return parse_summary_json(str(reduce_res.data.get("text") or ""))
                    except Exception:
                        pass
                llm_out = heuristic_title_summary(joined or text)
                emit_status(
                    orch,
                    run_id=run_id,
                    skill_name=skill_name,
                    message=f"Summary fallback heuristic after chunking for id={doc_id or 'unknown'}",
                    level="warn",
                    stage="fallback",
                    log_fn=log_fn,
                )
                return llm_out
            llm_out = heuristic_title_summary(text)
            emit_status(
                orch,
                run_id=run_id,
                skill_name=skill_name,
                message=f"Summary fallback heuristic for id={doc_id or 'unknown'}",
                level="warn",
                stage="fallback",
                log_fn=log_fn,
            )
            return llm_out

        if llm_res is None:
            llm_res = _call_llm(prompt)
        if not llm_res.ok:
            llm_out = heuristic_title_summary(text)
            emit_status(
                orch,
                run_id=run_id,
                skill_name=skill_name,
                message=f"Summary fallback heuristic for id={doc_id or 'unknown'}",
                level="warn",
                stage="fallback",
                log_fn=log_fn,
            )
            return llm_out

        llm_text = str(llm_res.data.get("text") or "")
        try:
            return parse_summary_json(llm_text)
        except Exception:
            tiny_prompt = prompt[:600]
            llm_retry = _call_llm(tiny_prompt, "parse_fail")
            if not llm_retry.ok:
                llm_out = heuristic_title_summary(text)
                emit_status(
                    orch,
                    run_id=run_id,
                    skill_name=skill_name,
                    message=f"Summary fallback heuristic for id={doc_id or 'unknown'}",
                    level="warn",
                    stage="fallback",
                    log_fn=log_fn,
                )
                return llm_out
            retry_text = str(llm_retry.data.get("text") or "")
            try:
                return parse_summary_json(retry_text)
            except Exception:
                llm_out = heuristic_title_summary(text)
                emit_status(
                    orch,
                    run_id=run_id,
                    skill_name=skill_name,
                    message=f"Summary fallback heuristic for id={doc_id or 'unknown'}",
                    level="warn",
                    stage="fallback",
                    log_fn=log_fn,
                )
                return llm_out
