from __future__ import annotations
import argparse
import os
from pathlib import Path
from typing import Any
import anyio
from mcp.server.fastmcp import FastMCP
from agentlab.services.operations import (
    OpsContext,
    build_embeddings as svc_build_embeddings,
    build_dashboard as svc_build_dashboard,
    cleanup_db as svc_cleanup_db,
    create_idea as svc_create_idea,
    create_skill as svc_create_skill,
    delete_duplicate_documents as svc_delete_duplicate_documents,
    demo_seed as svc_demo_seed,
    embeddings_status as svc_embeddings_status,
    fetch_and_index_urls as svc_fetch_and_index_urls,
    fetch_run as svc_fetch_run,
    index_docs as svc_index_docs,
    init_db as svc_init_db,
    judge_validity_report as svc_judge_validity_report,
    list_document_duplicates as svc_list_document_duplicates,
    list_runs as svc_list_runs,
    list_skills as svc_list_skills,
    load_run as svc_load_run,
    match_all_docs as svc_match_all_docs,
    match_all_ideas as svc_match_all_ideas,
    match_single_doc as svc_match_single_doc,
    match_single_idea as svc_match_single_idea,
    plan_assign as svc_plan_assign,
    plan_backlog as svc_plan_backlog,
    plan_match as svc_plan_match,
    plan_update as svc_plan_update,
    query_rows as svc_query_rows,
    resummarize_documents as svc_resummarize_documents,
    search_local as svc_search_local,
    search_semantic as svc_search_semantic,
    search_web as svc_search_web,
    validate_environment as svc_validate_environment,
)
from agentlab.tools.env_tools import env_check_db as tool_env_check_db
from agentlab.tools.env_tools import env_check_llm as tool_env_check_llm
from agentlab.tools.dedup_tools import delete_duplicate_documents as tool_delete_duplicate_documents
from agentlab.tools.file_tools import list_files as tool_list_files
from agentlab.tools.file_tools import read_file as tool_read_file
from agentlab.tools.file_tools import write_file as tool_write_file
from agentlab.tools.index_tools import index_document as tool_index_document
from agentlab.tools.index_tools import index_idea as tool_index_idea
from agentlab.tools.judge_tools import judge_validity_tool as tool_judge_validity
from agentlab.tools.llm_generate import llm_generate as tool_llm_generate
from agentlab.tools.local_exec import local_exec as tool_local_exec
from agentlab.tools.match_tools import match_doc_to_ideas as tool_match_doc_to_ideas
from agentlab.tools.match_tools import match_idea_to_docs as tool_match_idea_to_docs
from agentlab.tools.ops_tools import ops_log as tool_ops_log
from agentlab.tools.plan_tools import plan_assign_agent_tool as tool_plan_assign_agent
from agentlab.tools.plan_tools import plan_match_execution_tool as tool_plan_match_execution
from agentlab.tools.plan_tools import plan_update_status_tool as tool_plan_update_status
from agentlab.tools.sqlite_tools import delete_rows as tool_delete_rows
from agentlab.tools.sqlite_tools import migrate_db as tool_migrate_db
from agentlab.tools.sqlite_tools import persist_rows as tool_persist_rows
from agentlab.tools.sqlite_tools import query_rows as tool_query_rows
from agentlab.tools.sqlite_tools import update_rows as tool_update_rows
from agentlab.tools.types import ToolResult
from agentlab.tools.vector_tools import vector_index as tool_vector_index
from agentlab.tools.vector_tools import vector_query as tool_vector_query
from agentlab.tools.vector_tools import vector_stats as tool_vector_stats
from agentlab.tools.web_tools import fetch_url as tool_fetch_url

mcp = FastMCP("agentlab-v0")
WS = Path("workspace")
MIGRATIONS_DIR = Path("db/migrations")
DB_PATH = WS / "index" / "agent.db"


def _tool_result(result: ToolResult) -> dict[str, Any]:
    return {"ok": result.ok, "data": result.data or {}, "error": result.error}


async def _run_websocket(host: str, port: int, ws_path: str) -> None:
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import WebSocketRoute
    from mcp.server.websocket import websocket_server

    async def ws_endpoint(websocket):
        async with websocket_server(websocket.scope, websocket.receive, websocket.send) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )

    app = Starlette(routes=[WebSocketRoute(ws_path, ws_endpoint)])
    config = uvicorn.Config(app, host=host, port=port, log_level=mcp.settings.log_level.lower())
    server = uvicorn.Server(config)
    await server.serve()

@mcp.tool()
def search_web(query: str, top_n: int = 10) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    result = svc_search_web(ctx, query, WS, top_n=top_n)
    return {"query": query, "results": [h.__dict__ for h in result["hits"]]}

@mcp.tool()
def list_skills() -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    skills = svc_list_skills(ctx, Path("skills"))
    return {"skills": skills}

@mcp.tool()
def init_workspace() -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    db_path = svc_init_db(ctx, WS, MIGRATIONS_DIR)
    return {"db_path": str(db_path)}

@mcp.tool()
def runs_list(limit: int = 50) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    runs = svc_list_runs(ctx, WS, limit=limit)
    return {"runs": runs}

@mcp.tool()
def runs_show(run_id: str) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    run = svc_load_run(ctx, WS, run_id)
    return run

@mcp.tool()
def build_dashboard() -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    out = svc_build_dashboard(ctx, WS)
    return {"dashboard_path": str(out)}

@mcp.tool()
def validity_report() -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    result = svc_judge_validity_report(ctx, WS)
    return result

@mcp.tool()
def match_idea_to_docs_tool(idea_id: str, top_n: int = 10) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    rows = svc_query_rows(ctx, "SELECT id FROM ideas WHERE id = ? LIMIT 1", [idea_id], workspace=WS)
    if not rows:
        return {"error": f"idea not found: {idea_id}"}
    res = svc_match_single_idea(ctx, idea_id, WS, top_n=top_n)
    return {"idea_id": idea_id, "matches": res}

@mcp.tool()
def match_doc_to_ideas_tool(document_id: str, top_n: int = 10) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    rows = svc_query_rows(ctx, "SELECT id FROM documents WHERE id = ? LIMIT 1", [document_id], workspace=WS)
    if not rows:
        return {"error": f"doc not found: {document_id}"}
    res = svc_match_single_doc(ctx, document_id, WS, top_n=top_n)
    return {"document_id": document_id, "matches": res}

@mcp.tool()
def query_sql(sql: str) -> dict[str, Any]:
    if not sql.strip().lower().startswith("select"):
        return {"error": "Only SELECT allowed in v0"}
    ctx = OpsContext("agentlab-mcp", "mcp")
    rows = svc_query_rows(ctx, sql, [], workspace=WS)
    return {"rows": rows}

@mcp.tool()
def list_files(root: str, pattern: str = "**/*") -> dict[str, Any]:
    return _tool_result(tool_list_files(root, pattern=pattern))

@mcp.tool()
def read_file(path: str) -> dict[str, Any]:
    return _tool_result(tool_read_file(path))

@mcp.tool()
def write_file(path: str, content: str) -> dict[str, Any]:
    return _tool_result(tool_write_file(path, content))

@mcp.tool()
def query_rows(sql: str, params: list[Any] | None = None, db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_query_rows(sql, params=params or [], db_path=resolved))

@mcp.tool()
def persist_rows(table: str, rows: list[dict[str, Any]], mode: str = "insert", db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_persist_rows(table, rows, mode=mode, db_path=resolved))

@mcp.tool()
def update_rows(sql: str, params: list[Any] | None = None, db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_update_rows(sql, params=params or [], db_path=resolved))

@mcp.tool()
def delete_rows(sql: str, params: list[Any] | None = None, db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_delete_rows(sql, params=params or [], db_path=resolved))

@mcp.tool()
def migrate_db(workspace: str | None = None, migrations_dir: str | None = None) -> dict[str, Any]:
    resolved_ws = workspace or str(WS)
    resolved_migrations = migrations_dir or str(MIGRATIONS_DIR)
    return _tool_result(tool_migrate_db(resolved_ws, resolved_migrations))

@mcp.tool()
def index_document(doc_path: str) -> dict[str, Any]:
    return _tool_result(tool_index_document(doc_path))

@mcp.tool()
def index_idea(idea_path: str) -> dict[str, Any]:
    return _tool_result(tool_index_idea(idea_path))

@mcp.tool()
def local_exec(command: list[str], timeout_s: int = 60) -> dict[str, Any]:
    return _tool_result(tool_local_exec(command, timeout_s=timeout_s))

@mcp.tool()
def llm_generate(system: str, user: str, temperature: float = 0.2) -> dict[str, Any]:
    return _tool_result(tool_llm_generate(system, user, temperature=temperature))

@mcp.tool()
def ops_log(
    action: str,
    *,
    agent_name: str | None = None,
    agent_type: str | None = None,
    purpose: str | None = None,
    parent_run_id: str | None = None,
    run_id: str | None = None,
    status: str | None = None,
    tool_name: str | None = None,
    skill_name: str | None = None,
    parameters: dict[str, Any] | None = None,
    result_summary: str | None = None,
    duration_ms: int | None = None,
    with_agent: str | None = None,
    interaction_type: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _tool_result(
        tool_ops_log(
            action,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose=purpose,
            parent_run_id=parent_run_id,
            run_id=run_id,
            status=status,
            tool_name=tool_name,
            skill_name=skill_name,
            parameters=parameters,
            result_summary=result_summary,
            duration_ms=duration_ms,
            with_agent=with_agent,
            interaction_type=interaction_type,
            details=details,
        )
    )

@mcp.tool()
def fetch_url(url: str, timeout_s: int = 30, headers: dict[str, str] | None = None) -> dict[str, Any]:
    return _tool_result(tool_fetch_url(url, timeout_s=timeout_s, headers=headers))

@mcp.tool()
def vector_index(
    db_path: str | None = None,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 64,
    include_docs: bool = True,
    include_ideas: bool = True,
) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(
        tool_vector_index(
            resolved,
            model_name=model_name,
            batch_size=batch_size,
            include_docs=include_docs,
            include_ideas=include_ideas,
        )
    )

@mcp.tool()
def vector_query(
    query: str,
    db_path: str | None = None,
    limit: int = 20,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_vector_query(resolved, query, limit=limit, model_name=model_name))

@mcp.tool()
def vector_stats(db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_vector_stats(resolved))

@mcp.tool()
def env_check_db(min_free_mb: int = 50, db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_env_check_db(resolved, min_free_mb=min_free_mb))

@mcp.tool()
def env_check_llm(timeout_s: int = 2, auto_start: bool = False, start_wait_s: int = 2) -> dict[str, Any]:
    return _tool_result(tool_env_check_llm(timeout_s=timeout_s, auto_start=auto_start, start_wait_s=start_wait_s))

@mcp.tool()
def match_idea_to_docs(idea_id: str, top_n: int = 10, db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_match_idea_to_docs(idea_id, top_n=top_n, db_path=resolved))

@mcp.tool()
def match_doc_to_ideas(document_id: str, top_n: int = 10, db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_match_doc_to_ideas(document_id, top_n=top_n, db_path=resolved))

@mcp.tool()
def plan_match_execution(match_id: str, workspace: str | None = None) -> dict[str, Any]:
    return _tool_result(tool_plan_match_execution(workspace or str(WS), match_id))

@mcp.tool()
def plan_update_status(task_id: str, status: str, workspace: str | None = None) -> dict[str, Any]:
    return _tool_result(tool_plan_update_status(workspace or str(WS), task_id, status))

@mcp.tool()
def plan_assign_agent(task_id: str, agent: str, workspace: str | None = None) -> dict[str, Any]:
    return _tool_result(tool_plan_assign_agent(workspace or str(WS), task_id, agent))

@mcp.tool()
def judge_validity(db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_judge_validity(resolved))

@mcp.tool()
def search_local(query: str, limit: int = 20) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_search_local(ctx, query, WS, limit=limit)

@mcp.tool()
def search_semantic(query: str, limit: int = 20, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_search_semantic(ctx, query, WS, limit=limit, model_name=model_name)

@mcp.tool()
def build_embeddings(model_name: str = "sentence-transformers/all-MiniLM-L6-v2", batch_size: int = 64) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    result = svc_build_embeddings(ctx, WS, model_name=model_name, batch_size=batch_size)
    return result

@mcp.tool()
def embeddings_status() -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_embeddings_status(ctx, WS)

@mcp.tool()
def fetch_run(run_id: str, regenerate_summary: bool = False) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_fetch_run(ctx, run_id, WS, regenerate_summary=regenerate_summary)

@mcp.tool()
def fetch_and_index(urls: list[str], regenerate_summary: bool = False, prefer_chunking: bool = True) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_fetch_and_index_urls(
        ctx,
        urls,
        WS,
        regenerate_summary=regenerate_summary,
        prefer_chunking=prefer_chunking,
    )

@mcp.tool()
def index_docs(run_id: str) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    count = svc_index_docs(ctx, run_id, WS)
    return {"count": count}

@mcp.tool()
def create_idea(title: str, statement: str, proposed_by: str = "unknown") -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_create_idea(ctx, title, statement, proposed_by, WS)

@mcp.tool()
def match_all_ideas(top_n: int = 10) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    count = svc_match_all_ideas(ctx, WS, top_n=top_n)
    return {"count": count}

@mcp.tool()
def match_all_docs(top_n: int = 10) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    count = svc_match_all_docs(ctx, WS, top_n=top_n)
    return {"count": count}

@mcp.tool()
def plan_match(match_id: str) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    task_id = svc_plan_match(ctx, match_id, WS)
    return {"task_id": task_id}

@mcp.tool()
def plan_backlog() -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    tasks = svc_plan_backlog(ctx, WS)
    return {"tasks": tasks}

@mcp.tool()
def plan_update(task_id: str, status: str) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    svc_plan_update(ctx, task_id, status, WS)
    return {"task_id": task_id, "status": status}

@mcp.tool()
def plan_assign(task_id: str, agent: str) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    svc_plan_assign(ctx, task_id, agent, WS)
    return {"task_id": task_id, "agent": agent}

@mcp.tool()
def list_document_duplicates() -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    groups = svc_list_document_duplicates(ctx, WS)
    return {"groups": groups}

@mcp.tool()
def delete_document_duplicates(doc_ids: list[str], delete_files: bool = True) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_delete_duplicate_documents(ctx, WS, doc_ids, delete_files=delete_files)

@mcp.tool()
def delete_duplicate_documents(doc_ids: list[str], delete_files: bool = True, db_path: str | None = None) -> dict[str, Any]:
    resolved = db_path or str(DB_PATH)
    return _tool_result(tool_delete_duplicate_documents(resolved, doc_ids, delete_files=delete_files))

@mcp.tool()
def resummarize(only_missing: bool = True, limit: int | None = None, prefer_chunking: bool = True) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_resummarize_documents(
        ctx,
        WS,
        only_missing=only_missing,
        prefer_chunking=prefer_chunking,
        limit=limit,
    )

@mcp.tool()
def cleanup_db(dry_run: bool = True) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_cleanup_db(ctx, WS, dry_run=dry_run)

@mcp.tool()
def demo_seed() -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    svc_demo_seed(ctx, WS, MIGRATIONS_DIR)
    return {"status": "ok"}

@mcp.tool()
def validate_environment(require_llm: bool = True, min_free_mb: int = 50, auto_start: bool = True) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    return svc_validate_environment(ctx, workspace=WS, require_llm=require_llm, min_free_mb=min_free_mb, auto_start=auto_start)

@mcp.tool()
def create_skill(skill_name: str, description: str, body: str) -> dict[str, Any]:
    ctx = OpsContext("agentlab-mcp", "mcp")
    path = svc_create_skill(ctx, skill_name, description, body, Path("skills"))
    return {"path": str(path)}

def main():
    parser = argparse.ArgumentParser(description="Agent Lab MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http", "websocket"],
        default=os.getenv("AGENTLAB_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.getenv("AGENTLAB_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("AGENTLAB_MCP_PORT", "8000")))
    parser.add_argument("--mount-path", default=os.getenv("AGENTLAB_MCP_MOUNT_PATH", "/"))
    parser.add_argument("--streamable-path", default=os.getenv("AGENTLAB_MCP_STREAM_PATH", "/mcp"))
    parser.add_argument("--ws-path", default=os.getenv("AGENTLAB_MCP_WS_PATH", "/ws"))
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.settings.streamable_http_path = args.streamable_path

    if args.transport == "websocket":
        anyio.run(_run_websocket, args.host, args.port, args.ws_path)
    else:
        mcp.run(transport=args.transport, mount_path=args.mount_path)

if __name__ == "__main__":
    main()
