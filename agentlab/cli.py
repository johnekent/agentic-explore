from __future__ import annotations
import json
from pathlib import Path
import typer
from agentlab.core.paths import ensure_workspace
from agentlab.services.operations import (
    OpsContext,
    build_dashboard,
    build_embeddings as svc_build_embeddings,
    cleanup_db as svc_cleanup_db,
    create_idea as svc_create_idea,
    demo_seed as svc_demo_seed,
    fetch_run as svc_fetch_run,
    index_docs as svc_index_docs,
    init_db,
    judge_validity_report,
    match_all_docs as svc_match_all_docs,
    match_all_ideas as svc_match_all_ideas,
    plan_assign as svc_plan_assign,
    plan_backlog as svc_plan_backlog,
    plan_match as svc_plan_match,
    plan_update as svc_plan_update,
    search_local as svc_search_local,
    list_runs as svc_list_runs,
    load_run as svc_load_run,
    embeddings_status as svc_embeddings_status,
    search_semantic as svc_search_semantic,
    search_web as svc_search_web,
    resummarize_documents as svc_resummarize_documents,
)
from agentlab.agents.planner_orchestrator import build_planner


app = typer.Typer(add_completion=False)
WS_DEFAULT = Path("workspace")
MIGRATIONS_DIR = Path("db/migrations")

@app.command()
def init(workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    db_path = init_db(ctx, workspace, MIGRATIONS_DIR)
    typer.echo(f"Initialized DB at {db_path}")

@app.command()
def search(query: str, workspace: Path = WS_DEFAULT, top_n: int = 10):
    ctx = OpsContext("agentlab-cli", "cli")
    result = svc_search_web(ctx, query, workspace, top_n=top_n)
    typer.echo(f"run_id={result['run_id']}")
    typer.echo(result["run_path"])

@app.command("search-local")
def search_local(query: str, workspace: Path = WS_DEFAULT, limit: int = 20):
    ctx = OpsContext("agentlab-cli", "cli")
    result = svc_search_local(ctx, query, workspace, limit=limit)
    typer.echo("Documents:")
    for r in result["documents"]:
        typer.echo(f"- {r.get('title') or r.get('id')} (score={r.get('score')})")
        if r.get("url"):
            typer.echo(f"  {r.get('url')}")
    typer.echo("Ideas:")
    for r in result["ideas"]:
        typer.echo(f"- {r.get('title') or r.get('id')} (score={r.get('score')})")

runs_app = typer.Typer()
app.add_typer(runs_app, name="runs")

@runs_app.command("list")
def runs_list(workspace: Path = WS_DEFAULT, limit: int = 20):
    ctx = OpsContext("agentlab-cli", "cli")
    runs = svc_list_runs(ctx, workspace, limit=limit)
    for r in runs:
        typer.echo(f"{r.get('run_id')} topic={r.get('topic')} started_at={r.get('started_at')}")

@runs_app.command("show")
def runs_show(run_id: str, workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    run = svc_load_run(ctx, workspace, run_id)
    typer.echo(json.dumps(run, indent=2))

@app.command("search-semantic")
def search_semantic(query: str, workspace: Path = WS_DEFAULT, limit: int = 20, model_name: str = None):
    ctx = OpsContext("agentlab-cli", "cli")
    result = svc_search_semantic(ctx, query, workspace, limit=limit, model_name=model_name or "sentence-transformers/all-MiniLM-L6-v2")
    typer.echo("Documents:")
    for r in result["documents"]:
        typer.echo(f"- {r.get('title') or r.get('id')} (distance={r.get('distance')})")
        if r.get("url"):
            typer.echo(f"  {r.get('url')}")
    typer.echo("Ideas:")
    for r in result["ideas"]:
        typer.echo(f"- {r.get('title') or r.get('id')} (distance={r.get('distance')})")

embed_app = typer.Typer()
app.add_typer(embed_app, name="embed")

@embed_app.command("build")
def embed_build(
    workspace: Path = WS_DEFAULT,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 64,
    docs: bool = True,
    ideas: bool = True,
    debug: bool = False,
):
    ctx = OpsContext("agentlab-cli", "cli")
    log_fn = print if debug else None
    result = svc_build_embeddings(
        ctx,
        workspace,
        model_name=model_name,
        batch_size=batch_size,
        include_docs=docs,
        include_ideas=ideas,
        log_fn=log_fn,
    )
    typer.echo(f"Embedded docs={result['documents']} ideas={result['ideas']}")

@embed_app.command("status")
def embed_status(workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    result = svc_embeddings_status(ctx, workspace)
    typer.echo(f"Embeddings docs={result['documents']} ideas={result['ideas']}")

@app.command("resummarize-docs")
def resummarize_docs(workspace: Path = WS_DEFAULT, only_missing: bool = True, limit: int = 0, debug: bool = False):
    ctx = OpsContext("agentlab-cli", "cli")
    log_fn = print if debug else None
    result = svc_resummarize_documents(
        ctx,
        workspace,
        only_missing=only_missing,
        limit=(limit if limit > 0 else None),
        log_fn=log_fn,
    )
    typer.echo(f"Processed {result['processed']} updated {result['updated']} errors {result['errors']}")
@app.command()
def fetch(run_id: str, workspace: Path = WS_DEFAULT, regenerate_summary: bool = False):
    ctx = OpsContext("agentlab-cli", "cli")
    result = svc_fetch_run(ctx, run_id, workspace, regenerate_summary=regenerate_summary)
    typer.echo(f"created_docs={len(result['created_docs'])}")

index_app = typer.Typer()
app.add_typer(index_app, name="index")

@index_app.command("docs")
def index_docs(run_id: str, workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    count = svc_index_docs(ctx, run_id, workspace)
    typer.echo(f"Indexed {count} docs")

idea_app = typer.Typer()
app.add_typer(idea_app, name="idea")

@idea_app.command("create")
def idea_create(title: str, statement: str, proposed_by: str="unknown", workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    result = svc_create_idea(ctx, title, statement, proposed_by, workspace)
    typer.echo(f"idea_id={result['id']}")

match_app = typer.Typer()
app.add_typer(match_app, name="match")

@match_app.command("ideas")
def match_ideas(workspace: Path = WS_DEFAULT, top_n: int = 10, debug: bool = False):
    ctx = OpsContext("agentlab-cli", "cli")
    log_fn = print if debug else None
    count = svc_match_all_ideas(ctx, workspace, top_n=top_n, log_fn=log_fn)
    typer.echo(f"Matched {count} ideas")

@match_app.command("docs")
def match_docs(workspace: Path = WS_DEFAULT, top_n: int = 10, debug: bool = False):
    ctx = OpsContext("agentlab-cli", "cli")
    log_fn = print if debug else None
    count = svc_match_all_docs(ctx, workspace, top_n=top_n, log_fn=log_fn)
    typer.echo(f"Matched {count} docs")

judge_app = typer.Typer()
app.add_typer(judge_app, name="judge")

@judge_app.command("validity")
def judge_validity_cmd(workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    result = judge_validity_report(ctx, workspace)
    typer.echo(result["path"])

dash_app = typer.Typer()
app.add_typer(dash_app, name="dashboard")

@dash_app.command("build")
def dashboard_build(workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    out = build_dashboard(ctx, workspace)
    typer.echo(str(out))

plan_app = typer.Typer()
app.add_typer(plan_app, name="plan")

@plan_app.command("match")
def plan_match(match_id: str, workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    task_id = svc_plan_match(ctx, match_id, workspace)
    typer.echo(f"Created task {task_id} for match {match_id}")

@plan_app.command("backlog")
def plan_backlog(workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    tasks = svc_plan_backlog(ctx, workspace)
    for t in tasks:
        typer.echo(f"Task {t['id']}: {t['description']} (match: {t['match_id'] or 'N/A'}, status: {t['status']}, priority: {t['priority']}, assigned: {t['assigned_agent'] or 'None'})")

@plan_app.command("update-status")
def plan_update_status(task_id: str, status: str, workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    svc_plan_update(ctx, task_id, status, workspace)
    typer.echo(f"Updated task {task_id} to status {status}")

@plan_app.command("assign")
def plan_assign(task_id: str, agent: str, workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    svc_plan_assign(ctx, task_id, agent, workspace)
    typer.echo(f"Assigned task {task_id} to agent {agent}")

demo_app = typer.Typer()
app.add_typer(demo_app, name="demo")


@app.command("cleanup-db")
def cleanup_db(
    workspace: Path = WS_DEFAULT,
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Preview deletions or apply them."),
):
    ctx = OpsContext("agentlab-cli", "cli")
    report = svc_cleanup_db(ctx, workspace, dry_run=dry_run)
    typer.echo(json.dumps(report, indent=2))

@demo_app.command("seed")
def demo_seed(workspace: Path = WS_DEFAULT):
    ctx = OpsContext("agentlab-cli", "cli")
    svc_demo_seed(ctx, workspace, MIGRATIONS_DIR)
    typer.echo("Seeded demo ideas + docs.")


if __name__ == "__main__":
    app()
@app.command("run")
def run_local():
    planner = build_planner()
    typer.echo("Planner initialized. Use specific commands to run skills.")
