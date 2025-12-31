import streamlit as st
import pandas as pd
from pathlib import Path
from agentlab.services.operations import (
    OpsContext,
    build_dashboard,
    build_embeddings,
    create_idea,
    create_skill,
    embeddings_status,
    fetch_and_index_urls,
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

st.title("Agent Lab UI")

tabs = st.tabs(["Search", "Fetch & Index", "Match & Dashboard", "Planning", "Skills", "Duplicates", "Ops", "DB Viewer", "Add Idea"])

with tabs[0]:
    st.header("Search")
    st.subheader("Web Search")
    query = st.text_input("Query", key="web_query")
    top_n = st.slider("Top N", 1, 20, 10, key="web_top_n")
    if st.button("Search Web"):
        if query:
            result = search_web(ctx, query, ws, top_n=top_n)
            st.session_state["search_results"] = result["hits"]
            st.session_state["search_run_id"] = result["run_id"]
            st.success(f"Found {len(result['hits'])} results")
        else:
            st.error("Enter a query")

    if "search_results" in st.session_state:
        df = pd.DataFrame([h.__dict__ for h in st.session_state["search_results"]])
        st.dataframe(df)

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
        if st.button("Build Embeddings"):
            try:
                status = st.status("Building embeddings...", expanded=True)
                log_fn, logs = make_status_logger(status)
                result = build_embeddings(ctx, ws, model_name=model_name, log_fn=log_fn)
                status.update(label="Embeddings complete.", state="complete")
                st.session_state["semantic_embed_logs"] = logs
                st.success(f"Embedded docs={result['documents']} ideas={result['ideas']}")
            except Exception as exc:
                status.update(label="Embeddings failed.", state="error")
                st.error(f"Embedding build failed: {exc}")
        if st.button("Check Embedding Status"):
            try:
                status = embeddings_status(ctx, ws)
                st.session_state["semantic_embed_status"] = status
            except Exception as exc:
                st.error(f"Status check failed: {exc}")

    if "semantic_embed_status" in st.session_state:
        st.info(f"Embeddings docs={st.session_state['semantic_embed_status']['documents']} ideas={st.session_state['semantic_embed_status']['ideas']}")
    if "semantic_embed_logs" in st.session_state:
        st.subheader("Embedding Build Logs")
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

with tabs[1]:
    st.header("Fetch & Index Documents")
    try:
        runs = list_runs(ctx, ws, limit=25)
        if runs:
            run_options = []
            for r in runs:
                run_id = r.get("run_id")
                topic = r.get("topic") or ""
                started_at = r.get("started_at") or ""
                run_options.append((run_id, f"{run_id} | {topic} | {started_at}"))
            selected_label = st.selectbox(
                "Select Run",
                [label for _, label in run_options],
                index=0,
                key="fetch_run_select",
            )
            selected_run_id = None
            for rid, label in run_options:
                if label == selected_label:
                    selected_run_id = rid
                    break
            if selected_run_id:
                st.session_state["loaded_run"] = load_run(ctx, ws, selected_run_id)
        else:
            st.info("No runs found.")
    except Exception as exc:
        st.error(f"Run listing failed: {exc}")

    if 'search_results' in st.session_state or "loaded_run" in st.session_state:
        urls = []
        if 'search_results' in st.session_state:
            urls.extend([h.url for h in st.session_state['search_results']])
        if "loaded_run" in st.session_state:
            urls.extend([c.get("url") for c in st.session_state["loaded_run"].get("outputs", {}).get("candidates", [])])
        urls = [u for u in urls if u]
        select_all = st.checkbox("Select all URLs", key="select_all_urls")
        if select_all:
            st.session_state["fetch_urls_selected"] = urls
        selected = st.multiselect(
            "Select URLs to fetch",
            urls,
            key="fetch_urls_selected",
        )
        regenerate = st.checkbox("Regenerate title/summary (LLM)", key="fetch_regen")
        chunking = st.checkbox("Prefer chunked summarization", value=True, key="fetch_chunking")
        if st.button("Fetch & Index"):
            status = st.status("Fetching and indexing...", expanded=True)
            log_fn, _ = make_status_logger(status)
            result = fetch_and_index_urls(
                ctx,
                selected,
                ws,
                regenerate_summary=regenerate,
                prefer_chunking=chunking,
                log_fn=log_fn,
            )
            status.update(label="Fetch/index complete.", state="complete")
            if result["fetched"] > 0:
                st.success(f"Fetched and indexed {result['fetched']} documents")
            if result["failed_urls"]:
                st.warning("Failed to fetch some URLs:")
                for fail in result["failed_urls"]:
                    st.write(fail)
    else:
        st.info("Search first")

with tabs[2]:
    st.header("Match Ideas & Build Dashboard")
    if st.button("Match Ideas to Docs"):
        status = st.status("Matching ideas...", expanded=True)
        log_fn, _ = make_status_logger(status)
        count = match_all_ideas(ctx, ws, top_n=10, log_fn=log_fn)
        status.update(label="Matching complete.", state="complete")
        st.success(f"Matched {count} ideas")
        st.rerun()  # Refresh to update cache

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
    st.header("Planning & Task Management")

    # View Backlog
    st.subheader("Task Backlog")
    if st.button("Refresh Backlog"):
        st.rerun()
    tasks = plan_backlog(ctx, ws)
    if tasks:
        task_df = pd.DataFrame(tasks)
        st.dataframe(task_df)
    else:
        st.info("No active tasks.")

    # Create Task from Match
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

    # Update Task
    st.subheader("Update Task")
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

    # Gantt Chart
    st.subheader("Gantt Chart")
    if st.button("Generate Gantt Chart"):
        tasks = plan_backlog(ctx, ws)
        if tasks:
            import gantt
            from datetime import datetime, timedelta, date
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

with tabs[4]:
    st.header("Skills")
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

with tabs[5]:
    st.header("Duplicate Documents")
    if st.button("Check for Duplicates"):
        try:
            st.session_state["duplicate_groups"] = list_document_duplicates(ctx, ws)
        except Exception as exc:
            st.error(f"Duplicate check failed: {exc}")

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
            use_container_width=True,
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

with tabs[6]:
    st.header("Ops Dashboard")
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

with tabs[7]:
    st.header("DB Viewer")
    table = st.selectbox("Table", ["runs", "documents", "ideas", "matches", "tasks", "usage_logs", "agent_runs", "tool_calls", "agent_interactions"])
    df = load_table(table)
    st.dataframe(df)

with tabs[8]:
    st.header("Add Idea")
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
