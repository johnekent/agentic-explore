import json
import streamlit as st
import pandas as pd
from pathlib import Path
from agentlab.ui_helpers import (
    build_row_key,
    compute_fetch_status,
    compute_index_status,
    compute_summary_status,
    eligible_fetch,
    eligible_index,
    eligible_summarize,
)
from agentlab.services.operations import (
    OpsContext,
    build_dashboard,
    build_embeddings,
    create_idea,
    create_skill,
    embeddings_status,
    fetch_run,
    fetch_urls,
    index_documents,
    list_runs,
    list_skills,
    list_document_duplicates,
    delete_duplicate_documents,
    load_run,
    match_all_ideas,
    plan_assign,
    plan_backlog,
    plan_match,
    plan_update,
    query_rows,
    read_file,
    init_db,
    validate_environment,
    resummarize_documents,
    summarize_documents,
    search_local,
    search_semantic,
    search_web,
)

st.set_page_config(page_title="Agent Lab UI", layout="wide")

# Initialize workspace
ws = Path("workspace")
ctx = OpsContext("agentlab-ui", "ui")

# Apply migration if needed
migrations_dir = Path("db/migrations")
init_db(ctx, ws, migrations_dir)

# Load DB tables
def load_table(table_name):
    base_sql = f"SELECT * FROM {table_name}"
    sql = base_sql
    params: list[object] = []
    if table_name == "matches":
        sql = """
            SELECT m.id as match_id, i.title as idea_title, d.summary as doc_summary, m.match_score as match_score, m.reasons_json as reasons
            FROM matches m
            JOIN ideas i ON m.idea_id = i.id
            JOIN documents d ON m.document_id = d.id
        """
    elif table_name == "tasks":
        sql = base_sql
    elif table_name == "agent_runs":
        sql = "SELECT * FROM agent_runs ORDER BY started_at DESC"
    elif table_name == "tool_calls":
        sql = "SELECT * FROM tool_calls ORDER BY timestamp DESC"
    elif table_name == "agent_interactions":
        sql = "SELECT * FROM agent_interactions ORDER BY timestamp DESC"
    elif table_name == "usage_logs":
        sql = "SELECT * FROM usage_logs ORDER BY timestamp DESC"
    try:
        rows = query_rows(ctx, sql, params, workspace=ws)
    except Exception:
        if table_name == "matches":
            rows = query_rows(ctx, base_sql, params, workspace=ws)
        else:
            raise
    return pd.DataFrame(rows)


def make_status_logger(status):
    logs: list[str] = []

    def log(msg: str):
        logs.append(msg)
        status.write(msg)

    return log, logs

def build_lineage_text(
    run_id: str,
    runs_by_id: dict[str, dict],
    runs_by_parent: dict[str | None, list[dict]],
    tool_calls_by_run: dict[str, list[dict]],
    interactions_by_run: dict[str, list[dict]],
    depth: int = 0,
) -> list[str]:
    run = runs_by_id.get(run_id)
    if not run:
        return []
    prefix = "  " * depth
    lines = [f"{prefix}- run {run['id']} [{run['agent_name']}:{run['agent_type']}] {run['purpose'] or ''}"]
    for call in tool_calls_by_run.get(run["id"], []):
        lines.append(f"{prefix}  - tool {call['tool_name']} skill={call['skill_name'] or ''}")
    for inter in interactions_by_run.get(run["id"], []):
        if inter["interaction_type"] == "tool_call":
            continue
        lines.append(f"{prefix}  - interaction {inter['interaction_type']} with {inter['with_agent']}")
    for child in runs_by_parent.get(run["id"], []):
        lines.extend(build_lineage_text(child["id"], runs_by_id, runs_by_parent, tool_calls_by_run, interactions_by_run, depth + 1))
    return lines

def _safe_count(sql: str, params: list[object] | None = None) -> int | None:
    try:
        rows = query_rows(ctx, sql, params or [], workspace=ws)
        if not rows:
            return 0
        return int(rows[0].get("c") or 0)
    except Exception:
        return None


def get_pipeline_status() -> dict[str, int | None]:
    runs = 0
    run_hits = 0
    try:
        rows = query_rows(ctx, "SELECT outputs_json FROM runs", [], workspace=ws)
        runs = len(rows)
        for row in rows:
            outputs = json.loads(row.get("outputs_json") or "{}")
            candidates = outputs.get("candidates") or []
            summary = outputs.get("summary") or {}
            run_hits += len(candidates)
    except Exception:
        runs = None
        run_hits = None
    fetch_success = _safe_count(
        """
        SELECT COUNT(DISTINCT item_id) AS c
        FROM item_processing
        WHERE item_type = 'document'
          AND stage = 'fetch'
          AND status = 'success'
        """
    )
    index_success = _safe_count(
        """
        SELECT COUNT(DISTINCT item_id) AS c
        FROM item_processing
        WHERE item_type = 'document'
          AND stage = 'index'
          AND status = 'success'
        """
    )
    fetch_failed = _safe_count(
        """
        SELECT COUNT(DISTINCT item_id) AS c
        FROM item_processing
        WHERE item_type = 'document'
          AND stage = 'fetch'
          AND status IN ('failed', 'error')
        """
    )
    index_failed = _safe_count(
        """
        SELECT COUNT(DISTINCT item_id) AS c
        FROM item_processing
        WHERE item_type = 'document'
          AND stage = 'index'
          AND status IN ('failed', 'error')
        """
    )
    pending_index = _safe_count(
        """
        SELECT COUNT(DISTINCT f.item_id) AS c
        FROM item_processing f
        LEFT JOIN item_processing i
          ON f.item_id = i.item_id
          AND i.stage = 'index'
          AND i.status = 'success'
        WHERE f.item_type = 'document'
          AND f.stage = 'fetch'
          AND f.status = 'success'
          AND i.item_id IS NULL
        """
    )
    try:
        embed_status = embeddings_status(ctx, ws)
        doc_embeddings = embed_status.get("documents")
        idea_embeddings = embed_status.get("ideas")
    except Exception:
        doc_embeddings = None
        idea_embeddings = None
    return {
        "runs": runs,
        "run_hits": run_hits,
        "fetch_success": fetch_success,
        "index_success": index_success,
        "pending_index": pending_index,
        "fetch_failed": fetch_failed,
        "index_failed": index_failed,
        "documents": _safe_count("SELECT COUNT(*) AS c FROM documents"),
        "ideas": _safe_count("SELECT COUNT(*) AS c FROM ideas"),
        "matches": _safe_count("SELECT COUNT(*) AS c FROM matches"),
        "doc_embeddings": doc_embeddings,
        "idea_embeddings": idea_embeddings,
    }

st.title("Agent Lab UI")
st.markdown(
    "**Workflow:** 1) Source information  2) Identify work  3) Prioritize work  4) Track execution  5) Monitor ops"
)
pipeline = get_pipeline_status()

st.sidebar.header("Pipeline Status")
docs_total = pipeline.get("documents")
ideas_total = pipeline.get("ideas")
matches_total = pipeline.get("matches")
doc_embeds = pipeline.get("doc_embeddings")
idea_embeds = pipeline.get("idea_embeddings")
if st.sidebar.button("Refresh status"):
    st.rerun()
st.sidebar.caption("Flow: research trends -> fetch -> index -> identify -> prioritize -> track")
st.sidebar.metric("Web search runs", pipeline.get("runs") if pipeline.get("runs") is not None else "unknown")
st.sidebar.metric("Search hits (all runs)", pipeline.get("run_hits") if pipeline.get("run_hits") is not None else "unknown")
st.sidebar.metric("Fetched (success)", pipeline.get("fetch_success") if pipeline.get("fetch_success") is not None else "unknown")
st.sidebar.metric("Indexed (success)", pipeline.get("index_success") if pipeline.get("index_success") is not None else "unknown")
st.sidebar.metric("Pending index", pipeline.get("pending_index") if pipeline.get("pending_index") is not None else "unknown")
st.sidebar.metric("Fetch failed", pipeline.get("fetch_failed") if pipeline.get("fetch_failed") is not None else "unknown")
st.sidebar.metric("Index failed", pipeline.get("index_failed") if pipeline.get("index_failed") is not None else "unknown")
st.sidebar.metric("Indexed documents", docs_total if docs_total is not None else "unknown")
st.sidebar.metric("Ideas", ideas_total if ideas_total is not None else "unknown")
st.sidebar.metric("Matches", matches_total if matches_total is not None else "unknown")
if docs_total is not None and doc_embeds is not None:
    st.sidebar.write(f"Local search enabled (docs): {doc_embeds}/{docs_total}")
    st.sidebar.progress(0 if docs_total == 0 else min(1.0, doc_embeds / max(docs_total, 1)))
else:
    st.sidebar.write("Local search enabled (docs): unknown")
if ideas_total is not None and idea_embeds is not None:
    st.sidebar.write(f"Local search enabled (ideas): {idea_embeds}/{ideas_total}")
    st.sidebar.progress(0 if ideas_total == 0 else min(1.0, idea_embeds / max(ideas_total, 1)))
else:
    st.sidebar.write("Local search enabled (ideas): unknown")
st.sidebar.caption("Dependencies: fetch creates docs; index enables identify/matching.")

tabs = st.tabs([
    "1 Research Trends",
    "2 Idea Management",
    "3 Identify",
    "4 Prioritize",
    "5 Track",
    "Monitor",
])

with tabs[0]:
    st.header("Research Trends")
    st.subheader("Web Search")
    query = st.text_input("Query", key="web_query")
    top_n = st.slider("Top N", 1, 20, 10, key="web_top_n")
    if st.button("Search Web"):
        if query:
            result = search_web(ctx, query, ws, top_n=top_n)
            st.session_state["search_results"] = result["hits"]
            st.session_state["search_run_id"] = result["run_id"]
            st.success(f"Found {len(result['hits'])} results")
            st.rerun()
        else:
            st.error("Enter a query")

    if "search_results" in st.session_state:
        df = pd.DataFrame([h.__dict__ for h in st.session_state["search_results"]])
        st.dataframe(df)

    st.header("Sources")
    runs_rows = query_rows(
        ctx,
        "SELECT run_id, topic, started_at, outputs_json FROM runs ORDER BY started_at DESC LIMIT 200",
        [],
        workspace=ws,
    )
    fetch_logs = query_rows(
        ctx,
        """
        SELECT item_id, status, metadata_json, started_at
        FROM item_processing
        WHERE item_type = 'document'
          AND stage = 'fetch'
        ORDER BY started_at DESC
        LIMIT 1000
        """,
        [],
        workspace=ws,
    )
    summary_logs = query_rows(
        ctx,
        """
        SELECT item_id, status
        FROM item_processing
        WHERE item_type = 'document'
          AND stage = 'summary'
        """,
        [],
        workspace=ws,
    )
    index_logs = query_rows(
        ctx,
        """
        SELECT item_id, status
        FROM item_processing
        WHERE item_type = 'document'
          AND stage = 'index'
        """,
        [],
        workspace=ws,
    )
    doc_rows = query_rows(
        ctx,
        "SELECT id, title, url, summary, content_path, retrieved_at FROM documents ORDER BY retrieved_at DESC LIMIT 500",
        [],
        workspace=ws,
    )
    fetch_by_url = {}
    for row in fetch_logs:
        meta = {}
        raw_meta = row.get("metadata_json") or ""
        if raw_meta:
            try:
                meta = json.loads(raw_meta)
            except Exception:
                meta = {}
        url = meta.get("url")
        if url and url not in fetch_by_url:
            fetch_by_url[url] = {
                "item_id": row.get("item_id"),
                "status": row.get("status"),
                "path": meta.get("path"),
            }
    summary_success = {r.get("item_id") for r in summary_logs if r.get("status") == "success"}
    summary_failed = {r.get("item_id") for r in summary_logs if r.get("status") == "failed"}
    index_success = {r.get("item_id") for r in index_logs if r.get("status") == "success"}
    index_failed = {r.get("item_id") for r in index_logs if r.get("status") == "failed"}
    doc_by_url = {r.get("url"): r for r in doc_rows if r.get("url")}

    candidate_rows = []
    candidate_urls = set()
    session_results = st.session_state.get("search_results", [])
    session_run_id = st.session_state.get("search_run_id") or "session"
    for h in session_results:
        url = getattr(h, "url", None)
        if not url:
            continue
        candidate_urls.add(url)
        fetch_info = fetch_by_url.get(url, {})
        doc_row = doc_by_url.get(url, {})
        fetch_status = compute_fetch_status(fetch_info, doc_row)
        doc_id = fetch_info.get("item_id") or doc_row.get("id")
        summary_status = compute_summary_status(
            doc_id=doc_id,
            summary_success=summary_success,
            summary_failed=summary_failed,
            doc_row=doc_row,
        )
        index_status = compute_index_status(
            doc_id=doc_id,
            index_success=index_success,
            index_failed=index_failed,
        )
        candidate_rows.append(
            {
                "source_type": "url",
                "title": getattr(h, "title", "") or "",
                "url_or_path": url,
                "run_id": session_run_id,
                "topic": "",
                "fetch_status": fetch_status,
                "index_status": index_status,
                "content_path": fetch_info.get("path") or doc_row.get("content_path") or "",
            }
        )
    for r in runs_rows:
        outputs = {}
        raw_outputs = r.get("outputs_json") or ""
        if raw_outputs:
            try:
                outputs = json.loads(raw_outputs)
            except Exception:
                outputs = {}
        for c in outputs.get("candidates", []) or []:
            if not isinstance(c, dict):
                continue
            url = c.get("url")
            if not url:
                continue
            candidate_urls.add(url)
            fetch_info = fetch_by_url.get(url, {})
            doc_row = doc_by_url.get(url, {})
            fetch_status = compute_fetch_status(fetch_info, doc_row)
            doc_id = fetch_info.get("item_id") or doc_row.get("id")
            summary_status = compute_summary_status(
                doc_id=doc_id,
                summary_success=summary_success,
                summary_failed=summary_failed,
                doc_row=doc_row,
            )
            index_status = compute_index_status(
                doc_id=doc_id,
                index_success=index_success,
                index_failed=index_failed,
            )
            candidate_rows.append(
                {
                    "source_type": "url",
                    "title": c.get("title") or "",
                    "url_or_path": url,
                    "run_id": r.get("run_id") or "",
                    "topic": r.get("topic") or "",
                    "fetch_status": fetch_status,
                    "summary_status": summary_status,
                    "index_status": index_status,
                    "content_path": fetch_info.get("path") or doc_row.get("content_path") or "",
                }
            )

    extra_rows = []
    for d in doc_rows:
        url = d.get("url")
        if url and url in candidate_urls:
            continue
        source_type = "file" if not url else "url"
        fetch_status = "uploaded" if not url else "fetched"
        doc_id = d.get("id")
        summary_status = compute_summary_status(
            doc_id=doc_id,
            summary_success=summary_success,
            summary_failed=summary_failed,
            doc_row=d,
        )
        index_status = compute_index_status(
            doc_id=doc_id,
            index_success=index_success,
            index_failed=index_failed,
        )
        extra_rows.append(
            {
                "source_type": source_type,
                "title": d.get("title") or "",
                "url_or_path": url or d.get("content_path") or "",
                "run_id": "",
                "topic": "",
                "fetch_status": fetch_status,
                "summary_status": summary_status,
                "index_status": index_status,
                "content_path": d.get("content_path") or "",
            }
        )

    sources_df = pd.DataFrame(candidate_rows + extra_rows)
    if sources_df.empty:
        st.info("No sources found yet.")
    else:
        fetch_options = sorted(sources_df["fetch_status"].dropna().unique().tolist())
        summary_options = sorted(sources_df["summary_status"].dropna().unique().tolist())
        index_options = sorted(sources_df["index_status"].dropna().unique().tolist())
        fetch_filter, summary_filter, index_filter = st.columns(3)
        with fetch_filter:
            fetch_filter_vals = st.multiselect(
                "Filter by fetch status",
                fetch_options,
                default=fetch_options,
                key="sources_fetch_filter",
            )
        with summary_filter:
            summary_filter_vals = st.multiselect(
                "Filter by summary status",
                summary_options,
                default=summary_options,
                key="sources_summary_filter",
            )
        with index_filter:
            index_filter_vals = st.multiselect(
                "Filter by index status",
                index_options,
                default=index_options,
                key="sources_index_filter",
            )
        sources_df = sources_df.copy()
        sources_df["row_key"] = sources_df.apply(
            lambda row: build_row_key(
                source_type=str(row.get("source_type") or ""),
                url_or_path=str(row.get("url_or_path") or ""),
                run_id=str(row.get("run_id") or ""),
                content_path=str(row.get("content_path") or ""),
            ),
            axis=1,
        )
        filtered = sources_df[
            sources_df["fetch_status"].isin(fetch_filter_vals)
            & sources_df["summary_status"].isin(summary_filter_vals)
            & sources_df["index_status"].isin(index_filter_vals)
        ].copy()
        eligible_fetch_mask = filtered["fetch_status"].map(eligible_fetch)
        eligible_summarize_mask = filtered.apply(
            lambda row: eligible_summarize(
                str(row.get("fetch_status") or ""),
                str(row.get("summary_status") or ""),
                str(row.get("content_path") or ""),
            ),
            axis=1,
        )
        eligible_index_mask = filtered.apply(
            lambda row: eligible_index(
                str(row.get("summary_status") or ""),
                str(row.get("index_status") or ""),
                str(row.get("content_path") or ""),
            ),
            axis=1,
        )
        selection_state = st.session_state.get("sources_selection", {})
        filtered.insert(
            0,
            "select_fetch",
            filtered["row_key"].map(
                lambda key: bool(selection_state.get(key, {}).get("fetch", False))
            ),
        )
        filtered.insert(
            1,
            "select_summarize",
            filtered["row_key"].map(
                lambda key: bool(selection_state.get(key, {}).get("summarize", False))
            ),
        )
        filtered.insert(
            2,
            "select_index",
            filtered["row_key"].map(
                lambda key: bool(selection_state.get(key, {}).get("index", False))
            ),
        )
        filtered["fetch_action"] = eligible_fetch_mask.map(lambda ok: "eligible" if ok else "locked")
        filtered["summary_action"] = eligible_summarize_mask.map(
            lambda ok: "eligible" if ok else "locked"
        )
        filtered["index_action"] = eligible_index_mask.map(lambda ok: "eligible" if ok else "locked")
        select_fetch_col, select_sum_col, select_index_col = st.columns(3)
        with select_fetch_col:
            if st.button("Select all unfetched", key="sources_select_all_fetch"):
                for row_key, is_eligible in zip(filtered["row_key"], eligible_fetch_mask):
                    selection_state[row_key] = {
                        "fetch": bool(is_eligible),
                        "summarize": bool(selection_state.get(row_key, {}).get("summarize", False)),
                        "index": bool(selection_state.get(row_key, {}).get("index", False)),
                    }
                st.session_state["sources_selection"] = selection_state
                st.rerun()
        with select_sum_col:
            if st.button("Select all unsummarized", key="sources_select_all_summarize"):
                for row_key, is_eligible in zip(filtered["row_key"], eligible_summarize_mask):
                    selection_state[row_key] = {
                        "fetch": bool(selection_state.get(row_key, {}).get("fetch", False)),
                        "summarize": bool(is_eligible),
                        "index": bool(selection_state.get(row_key, {}).get("index", False)),
                    }
                st.session_state["sources_selection"] = selection_state
                st.rerun()
        with select_index_col:
            if st.button("Select all unindexed", key="sources_select_all_index"):
                for row_key, is_eligible in zip(filtered["row_key"], eligible_index_mask):
                    selection_state[row_key] = {
                        "fetch": bool(selection_state.get(row_key, {}).get("fetch", False)),
                        "summarize": bool(selection_state.get(row_key, {}).get("summarize", False)),
                        "index": bool(is_eligible),
                    }
                st.session_state["sources_selection"] = selection_state
                st.rerun()
        disabled_columns = [
            c
            for c in filtered.columns
            if c not in ["select_fetch", "select_summarize", "select_index"]
        ]
        edited = st.data_editor(
            filtered.drop(columns=["row_key"]),
            width="stretch",
            hide_index=True,
            disabled=disabled_columns,
            column_config={
                "select_fetch": st.column_config.CheckboxColumn("Fetch"),
                "select_summarize": st.column_config.CheckboxColumn("Summarize"),
                "select_index": st.column_config.CheckboxColumn("Index"),
            },
            key="sources_editor",
        )
        updated_selection = {}
        for _, row in edited.iterrows():
            row_key = build_row_key(
                source_type=str(row.get("source_type") or ""),
                url_or_path=str(row.get("url_or_path") or ""),
                run_id=str(row.get("run_id") or ""),
                content_path=str(row.get("content_path") or ""),
            )
            updated_selection[row_key] = {
                "fetch": bool(row.get("select_fetch"))
                if row.get("fetch_action") == "eligible"
                else False,
                "summarize": bool(row.get("select_summarize"))
                if row.get("summary_action") == "eligible"
                else False,
                "index": bool(row.get("select_index"))
                if row.get("index_action") == "eligible"
                else False,
            }
        st.session_state["sources_selection"] = updated_selection
        to_fetch = (
            edited[edited["select_fetch"] == True]  # noqa: E712
            .loc[lambda df: df["fetch_action"] == "eligible"]
            ["url_or_path"]
            .dropna()
            .tolist()
        )
        to_summarize = (
            edited[edited["select_summarize"] == True]  # noqa: E712
            .loc[lambda df: df["summary_action"] == "eligible"]
            ["content_path"]
            .dropna()
            .tolist()
        )
        to_index = (
            edited[edited["select_index"] == True]  # noqa: E712
            .loc[lambda df: df["index_action"] == "eligible"]
            ["content_path"]
            .dropna()
            .tolist()
        )
        (
            fetch_btn_col,
            fetch_opts_col,
            sum_btn_col,
            sum_opts_col,
            index_btn_col,
            index_opts_col,
        ) = st.columns([1, 2, 1, 2, 1, 2])
        with fetch_btn_col:
            fetch_clicked = st.button("Fetch selected", disabled=not to_fetch)
        with fetch_opts_col:
            st.caption("Fetch options: none")
        with sum_btn_col:
            summarize_clicked = st.button("Summarize selected", disabled=not to_summarize)
        with sum_opts_col:
            overwrite = st.checkbox("Overwrite existing title/summary", key="summary_overwrite")
            prefer_chunking = st.checkbox(
                "Prefer chunked summarization",
                value=False,
                key="summary_chunking",
            )
        with index_btn_col:
            index_clicked = st.button("Index selected", disabled=not to_index)
        with index_opts_col:
            st.caption("Index options: none")
        if fetch_clicked:
            status = st.status("Fetching...", expanded=True)
            log_fn, _ = make_status_logger(status)
            result = fetch_urls(
                ctx,
                to_fetch,
                ws,
                regenerate_summary=False,
                prefer_chunking=False,
                log_fn=log_fn,
            )
            status.update(label="Fetch complete.", state="complete")
            st.session_state["last_fetch_created"] = result.get("created_docs", [])
            if result["fetched"] > 0:
                st.success(f"Fetched {result['fetched']} documents")
            if result["failed_urls"]:
                st.warning("Failed to fetch some URLs:")
                for fail in result["failed_urls"]:
                    st.write(fail)
        if summarize_clicked:
            status = st.status("Summarizing...", expanded=True)
            log_fn, _ = make_status_logger(status)
            result = summarize_documents(
                ctx,
                to_summarize,
                ws,
                prefer_chunking=prefer_chunking,
                overwrite=overwrite,
                log_fn=log_fn,
            )
            status.update(label="Summarize complete.", state="complete")
            st.success(f"Summarized {result['summarized']} documents")
            if result.get("failed"):
                st.warning(f"Failed to summarize {result['failed']} documents")
        if index_clicked:
            status = st.status("Indexing...", expanded=True)
            result = index_documents(ctx, to_index, ws)
            status.update(label="Index complete.", state="complete")
            st.success(f"Indexed {result['indexed']} documents")
            if result.get("failed"):
                st.warning(f"Failed to index {result['failed']} documents")

with tabs[1]:
    st.header("Idea Management")
    title = st.text_input("Title")
    statement = st.text_area("Statement")
    if st.button("Add"):
        if title and statement:
            result = create_idea(ctx, title, statement, "ui", ws)
            st.write(f"Idea file created at: {result['path']}")
            st.success("Added")
            st.rerun()  # Refresh to update cache
        else:
            st.error("Fill fields")

with tabs[2]:
    st.header("Identify Possible Work")
    st.subheader("Local Search")
    search_mode = st.radio("Mode", ["Semantic (default)", "Keyword"], horizontal=True, key="local_mode")
    search_query = st.text_input("Search", key="local_query")
    search_limit = st.slider("Max Results Per Type", 5, 50, 20, key="local_limit")
    model_name = st.text_input("Embedding Model", "sentence-transformers/all-MiniLM-L6-v2", key="local_model")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Search Local"):
            if search_query:
                try:
                    if search_mode.startswith("Semantic"):
                        result = search_semantic(ctx, search_query, ws, limit=search_limit, model_name=model_name)
                    else:
                        result = search_local(ctx, search_query, ws, limit=search_limit)
                    st.session_state["local_search_results"] = result
                except Exception as exc:
                    st.error(f"Search failed: {exc}")
            else:
                st.error("Enter a search query")
    with col2:
        can_embed = (docs_total or 0) > 0 or (ideas_total or 0) > 0
        if st.button("Enable Local Search", disabled=not can_embed):
            try:
                status = st.status("Building local search index...", expanded=True)
                log_fn, logs = make_status_logger(status)
                result = build_embeddings(ctx, ws, model_name=model_name, log_fn=log_fn)
                status.update(label="Local search ready.", state="complete")
                st.session_state["semantic_embed_logs"] = logs
                st.success(f"Indexed docs={result['documents']} ideas={result['ideas']}")
                st.rerun()
            except Exception as exc:
                status.update(label="Local search indexing failed.", state="error")
                st.error(f"Local search indexing failed: {exc}")
        if not can_embed:
            st.caption("Local search requires at least one indexed document or idea.")
        if st.button("Check Embedding Status"):
            try:
                status = embeddings_status(ctx, ws)
                st.session_state["semantic_embed_status"] = status
            except Exception as exc:
                st.error(f"Status check failed: {exc}")

    if "semantic_embed_status" in st.session_state:
        st.info(f"Local search indexed docs={st.session_state['semantic_embed_status']['documents']} ideas={st.session_state['semantic_embed_status']['ideas']}")
    if "semantic_embed_logs" in st.session_state:
        st.subheader("Local Search Index Logs")
        st.text("\n".join(st.session_state["semantic_embed_logs"]))

    if "local_search_results" in st.session_state:
        res = st.session_state["local_search_results"]
        st.subheader("Documents")
        docs = res.get("documents", [])
        if docs:
            st.dataframe(pd.DataFrame(docs))
        else:
            st.info("No document matches.")
        st.subheader("Ideas")
        ideas = res.get("ideas", [])
        if ideas:
            st.dataframe(pd.DataFrame(ideas))
        else:
            st.info("No idea matches.")
    can_match = (docs_total or 0) > 0 and (ideas_total or 0) > 0
    if st.button("Match Ideas to Docs", disabled=not can_match):
        status = st.status("Matching ideas...", expanded=True)
        log_fn, _ = make_status_logger(status)
        count = match_all_ideas(ctx, ws, top_n=10, log_fn=log_fn)
        status.update(label="Matching complete.", state="complete")
        st.success(f"Matched {count} ideas")
        st.rerun()  # Refresh to update cache
    if not can_match:
        st.caption("Matching requires at least one document and one idea.")

    if st.button("Build Dashboard"):
        out = build_dashboard(ctx, ws)
        st.markdown(read_file(ctx, str(out)))

    st.subheader("Top Matches")
    matches_df = load_table("matches")
    if not matches_df.empty:
        st.dataframe(matches_df)
    else:
        st.info("No matches yet. Run matching first.")

    st.subheader("Re-summarize Documents")
    only_missing = st.checkbox("Only update missing title/summary", value=True, key="resum_only_missing")
    chunking = st.checkbox("Prefer chunked summarization", value=True, key="resum_chunking")
    limit = st.number_input("Limit (0 = no limit)", min_value=0, max_value=10000, value=0, step=1, key="resum_limit")
    if st.button("Re-summarize Documents"):
        try:
            status = st.status("Re-summarizing documents...", expanded=True)
            log_fn, logs = make_status_logger(status)
            result = resummarize_documents(
                ctx,
                ws,
                only_missing=only_missing,
                prefer_chunking=chunking,
                limit=(limit if limit > 0 else None),
                log_fn=log_fn,
            )
            status.update(label="Re-summarize complete.", state="complete")
            st.session_state["resum_logs"] = logs
            st.success(f"Processed {result['processed']} updated {result['updated']} errors {result['errors']}")
        except Exception as exc:
            status.update(label="Re-summarize failed.", state="error")
            st.error(f"Re-summarize failed: {exc}")
    if "resum_logs" in st.session_state:
        st.subheader("Re-summarize Logs")
        st.text("\n".join(st.session_state["resum_logs"]))

with tabs[3]:
    st.header("Prioritize Work")

    st.subheader("Create Task from Match")
    matches_df = load_table("matches")
    if not matches_df.empty:
        match_options = matches_df['match_id'].tolist()
        selected_match = st.selectbox("Select Match", match_options)
        if st.button("Create Task"):
            task_id = plan_match(ctx, selected_match, ws)
            st.success(f"Created task {task_id} for match {selected_match}")
            st.rerun()
    else:
        st.info("No matches available.")

    st.subheader("Update Task")
    tasks = plan_backlog(ctx, ws)
    if tasks:
        task_ids = [t['id'] for t in tasks]
        selected_task = st.selectbox("Select Task to Update", task_ids, key="update")
        new_status = st.selectbox("New Status", ["pending", "in_progress", "completed"], key="status")
        if st.button("Update Status"):
            plan_update(ctx, selected_task, new_status, ws)
            st.success(f"Updated task {selected_task} to {new_status}")
            st.rerun()

        agent = st.text_input("Assign Agent", key="agent")
        if st.button("Assign Agent"):
            plan_assign(ctx, selected_task, agent, ws)
            st.success(f"Assigned {agent} to task {selected_task}")
            st.rerun()
    else:
        st.info("No active tasks.")

with tabs[4]:
    st.header("Track Execution")
    st.subheader("Task Backlog")
    if st.button("Refresh Backlog"):
        st.rerun()
    tasks = plan_backlog(ctx, ws)
    if tasks:
        task_df = pd.DataFrame(tasks)
        st.dataframe(task_df)
    else:
        st.info("No active tasks.")

    st.subheader("Gantt Chart")
    if st.button("Generate Gantt Chart"):
        tasks = plan_backlog(ctx, ws)
        if tasks:
            import gantt
            from datetime import datetime, date
            p = gantt.Project(name='Agent Lab Tasks')
            for t in tasks:
                start = datetime.fromisoformat(t['created_at']).date()
                duration = 7 if t['priority'] == 'high' else 5 if t['priority'] == 'medium' else 3
                task_pg = gantt.Task(name=t['description'][:20], start=start, duration=duration)  # Truncate name
                p.add_task(task_pg)
            p.make_svg_for_tasks(filename='gantt.svg', today=date.today())
            svg_content = read_file(ctx, "gantt.svg")
            import re
            svg_content = re.sub(r'<svg([^>]*)>', r'<svg\1 style="width: 100%; height: auto;">', svg_content)
            import streamlit.components.v1 as components
            components.html(f"<div style='overflow-x: auto; width: 100%;'>{svg_content}</div>", height=600)
        else:
            st.info("No tasks to display.")

with tabs[5]:
    st.header("Monitor")
    st.subheader("Environment Validation")
    require_llm = st.checkbox("Require LLM (Ollama)", value=True, key="env_require_llm")
    auto_start = st.checkbox("Auto-start Ollama if stopped", value=True, key="env_auto_start")
    min_free_mb = st.number_input("Min free disk (MB)", min_value=10, max_value=10240, value=50, step=10, key="env_min_free")
    if st.button("Validate Environment"):
        status = st.status("Validating environment...", expanded=True)
        status.write("Checking workspace DB and disk space.")
        status.write("Checking LLM provider and attempting auto-start if needed.")
        try:
            result = validate_environment(
                ctx,
                workspace=ws,
                require_llm=require_llm,
                auto_start=auto_start,
                min_free_mb=min_free_mb,
            )
            status.update(label="Environment checks passed.", state="complete")
            st.json(result)
        except Exception as exc:
            status.update(label="Environment validation failed.", state="error")
            st.error(f"Environment validation failed: {exc}")

    st.subheader("Duplicate Documents")
    can_dedup = (docs_total or 0) > 0
    if st.button("Check for Duplicates", disabled=not can_dedup):
        try:
            st.session_state["duplicate_groups"] = list_document_duplicates(ctx, ws)
        except Exception as exc:
            st.error(f"Duplicate check failed: {exc}")
    if not can_dedup:
        st.caption("Duplicate checks require indexed documents.")

    groups = st.session_state.get("duplicate_groups", [])
    if groups:
        rows = []
        for group in groups:
            for doc in group["docs"]:
                rows.append(
                    {
                        "duplicate_key": group["key"],
                        "reason": group["reason"],
                        "doc_id": doc.get("id"),
                        "title": doc.get("title"),
                        "summary": doc.get("summary"),
                        "url": doc.get("url"),
                        "content_path": doc.get("content_path"),
                    }
                )
        dup_df = pd.DataFrame(rows).sort_values(by=["duplicate_key", "doc_id"]).reset_index(drop=True)
        st.subheader("Potential Duplicates")
        edit_df = dup_df.copy()
        edit_df["delete"] = False
        edited = st.data_editor(
            edit_df,
            width="stretch",
            num_rows="fixed",
            hide_index=True,
            column_config={"delete": st.column_config.CheckboxColumn("Delete")},
            key="dup_editor",
        )
        selected_ids = edited[edited["delete"]]["doc_id"].tolist()
        if st.button("Delete Selected Duplicates", key="dup_delete"):
            if selected_ids:
                try:
                    result = delete_duplicate_documents(ctx, ws, selected_ids, delete_files=True)
                    st.success(f"Deleted {result['deleted']} docs, files {result['files_deleted']}")
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")
            else:
                st.info("Select at least one document ID.")
    else:
        st.info("No duplicates loaded.")
    runs_df = load_table("agent_runs")
    calls_df = load_table("tool_calls")
    interactions_df = load_table("agent_interactions")
    if not runs_df.empty:
        st.subheader("Recent runs")
        st.dataframe(runs_df)
    else:
        st.info("No runs logged yet.")
    if not calls_df.empty:
        st.subheader("Recent tool calls")
        st.dataframe(calls_df)
    else:
        st.info("No tool calls logged yet.")
    if not interactions_df.empty:
        st.subheader("Agent interactions")
        st.dataframe(interactions_df)
    else:
        st.info("No interactions logged yet.")

    st.subheader("Performance Report")
    perf_df = load_table("perf_spans")
    if perf_df.empty:
        st.info("No performance spans logged yet.")
    else:
        perf_df["duration_ms"] = pd.to_numeric(perf_df.get("duration_ms"), errors="coerce").fillna(0).astype(int)
        run_ids = sorted(perf_df.get("run_id", pd.Series(dtype=str)).dropna().unique().tolist())
        run_filter = st.selectbox("Filter by run", ["(all)"] + run_ids, key="perf_run_filter")
        if run_filter != "(all)":
            perf_df = perf_df[perf_df["run_id"] == run_filter]
        grouped = (
            perf_df.groupby(["span_name", "skill_name", "span_category", "status"])["duration_ms"]
            .agg(
                count="count",
                avg_ms="mean",
                p95_ms=lambda s: s.quantile(0.95),
                max_ms="max",
            )
            .reset_index()
            .sort_values(by="p95_ms", ascending=False)
        )
        st.dataframe(grouped.head(50))
        st.caption("Durations are in milliseconds; p95 is per span group.")
        slowest = perf_df.sort_values(by="duration_ms", ascending=False).head(50)
        st.subheader("Slowest spans")
        st.dataframe(
            slowest[
                [
                    "span_name",
                    "skill_name",
                    "span_category",
                    "duration_ms",
                    "run_id",
                    "status",
                    "started_at",
                ]
            ]
        )

    st.subheader("Lineage")
    if runs_df.empty:
        st.info("No runs to show lineage.")
    else:
        runs = runs_df.to_dict(orient="records")
        tool_calls = calls_df.to_dict(orient="records") if not calls_df.empty else []
        interactions = interactions_df.to_dict(orient="records") if not interactions_df.empty else []
        runs_by_parent: dict[str | None, list[dict]] = {}
        runs_by_id: dict[str, dict] = {}
        for r in runs:
            runs_by_id[r["id"]] = r
            runs_by_parent.setdefault(r.get("parent_run_id"), []).append(r)
        tool_calls_by_run: dict[str, list[dict]] = {}
        for c in tool_calls:
            tool_calls_by_run.setdefault(c["run_id"], []).append(c)
        interactions_by_run: dict[str, list[dict]] = {}
        for i in interactions:
            interactions_by_run.setdefault(i["run_id"], []).append(i)
        root_ids = [r["id"] for r in runs if not r.get("parent_run_id")]
        for root_id in root_ids[:5]:
            lines = build_lineage_text(root_id, runs_by_id, runs_by_parent, tool_calls_by_run, interactions_by_run)
            st.code("\n".join(lines) if lines else "(no lineage)")

    st.subheader("Skills")
    try:
        skills = list_skills(ctx, Path("skills"))
        if skills:
            st.subheader("Installed Skills")
            st.dataframe(pd.DataFrame(skills))
        else:
            st.info("No skills found.")
    except Exception as exc:
        st.error(f"Skill listing failed: {exc}")

    st.subheader("Create Skill")
    skill_name = st.text_input("Skill Name (lowercase, hyphens)")
    skill_desc = st.text_area("Description (used for triggering)")
    skill_body = st.text_area("SKILL.md Body", height=200, value="# Instructions\n")
    if st.button("Create Skill"):
        try:
            skill_path = create_skill(ctx, skill_name, skill_desc, skill_body, Path("skills"))
            st.success(f"Created {skill_path}")
        except Exception as exc:
            st.error(f"Skill creation failed: {exc}")

    st.subheader("View Skill.md")
    if skills:
        selected_skill = st.selectbox("Select Skill", [s["path"] for s in skills], key="skill_view_select")
        if selected_skill:
            try:
                content = read_file(ctx, selected_skill)
                st.code(content, language="markdown")
            except Exception as exc:
                st.error(f"Failed to load SKILL.md: {exc}")

    st.subheader("DB Viewer")
    table = st.selectbox(
        "Table",
        [
            "runs",
            "documents",
            "item_processing",
            "ideas",
            "matches",
            "tasks",
            "usage_logs",
            "agent_runs",
            "tool_calls",
            "agent_interactions",
            "perf_spans",
        ],
    )
    df = load_table(table)
    st.dataframe(df)
