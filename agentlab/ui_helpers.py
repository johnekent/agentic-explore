from __future__ import annotations


def build_row_key(
    *,
    source_type: str,
    url_or_path: str,
    run_id: str,
    content_path: str,
) -> str:
    return f"{source_type}|{url_or_path}|{run_id}|{content_path}"


def compute_fetch_status(fetch_info: dict | None, doc_row: dict | None) -> str:
    fetch_info = fetch_info or {}
    doc_row = doc_row or {}
    status = fetch_info.get("status")
    if status == "success":
        return "fetched"
    if status == "failed":
        return "fetch_failed"
    if status:
        return str(status)
    if doc_row:
        return "fetched"
    return "not_fetched"


def compute_summary_status(
    *,
    doc_id: str | None,
    summary_success: set[str],
    summary_failed: set[str],
    doc_row: dict | None,
) -> str:
    if doc_id and doc_id in summary_success:
        return "summarized"
    if doc_id and doc_id in summary_failed:
        return "summary_failed"
    if doc_row and str(doc_row.get("summary") or "").strip():
        return "summarized"
    return "not_summarized"


def compute_index_status(
    *,
    doc_id: str | None,
    index_success: set[str],
    index_failed: set[str],
) -> str:
    if doc_id and doc_id in index_success:
        return "indexed"
    if doc_id and doc_id in index_failed:
        return "index_failed"
    return "not_indexed"


def eligible_fetch(fetch_status: str) -> bool:
    return fetch_status in {"not_fetched", "fetch_failed"}


def eligible_summarize(fetch_status: str, summary_status: str, content_path: str) -> bool:
    return (
        fetch_status in {"fetched", "skipped_already_fetched", "uploaded"}
        and summary_status in {"not_summarized", "summary_failed"}
        and bool(str(content_path or "").strip())
    )


def eligible_index(summary_status: str, index_status: str, content_path: str) -> bool:
    return (
        summary_status == "summarized"
        and index_status in {"not_indexed", "index_failed"}
        and bool(str(content_path or "").strip())
    )
