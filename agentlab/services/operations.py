from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentlab.db.db import apply_migrations_from_dir, connect
from agentlab.orchestrator.runtime import default_orchestrator
from agentlab.pipeline.embeddings import DEFAULT_EMBED_MODEL
from agentlab.skills_runtime.operations_skills import (
    BuildDashboard as BuildDashboardSkill,
    BuildEmbeddings as BuildEmbeddingsSkill,
    CleanupContent as CleanupContentSkill,
    CleanupDb as CleanupDbSkill,
    DeleteAllData as DeleteAllDataSkill,
    CreateIdea as CreateIdeaSkill,
    CreateSkill as CreateSkillSkill,
    DeleteDuplicateDocuments as DeleteDuplicateDocumentsSkill,
    DemoSeed as DemoSeedSkill,
    EmbeddingsStatus as EmbeddingsStatusSkill,
    FetchUrls as FetchUrlsSkill,
    IndexDocuments as IndexDocumentsSkill,
    InitWorkspace as InitWorkspaceSkill,
    JudgeValidity as JudgeValiditySkill,
    ListDocumentDuplicates as ListDocumentDuplicatesSkill,
    ListRuns as ListRunsSkill,
    ListSkills as ListSkillsSkill,
    LoadRun as LoadRunSkill,
    MatchLearning as MatchLearningSkill,
    MatchAllDocs as MatchAllDocsSkill,
    MatchAllIdeas as MatchAllIdeasSkill,
    MatchSingleDoc as MatchSingleDocSkill,
    MatchSingleIdea as MatchSingleIdeaSkill,
    SummarizeDocuments as SummarizeDocumentsSkill,
    PlanAssign as PlanAssignSkill,
    PlanBacklog as PlanBacklogSkill,
    PlanMatch as PlanMatchSkill,
    PlanUpdate as PlanUpdateSkill,
    QueryRows as QueryRowsSkill,
    ReadFile as ReadFileSkill,
    ResummarizeDocuments as ResummarizeDocumentsSkill,
    SearchLocal as SearchLocalSkill,
    SearchSemantic as SearchSemanticSkill,
    ValidateEnvironment as ValidateEnvironmentSkill,
)
from agentlab.skills_runtime.search_pipeline import FetchDocumentsFromRun, IndexDocumentsFromRun, SearchWebSources


@dataclass(frozen=True)
class OpsContext:
    agent_name: str
    agent_type: str
    parent_run_id: str | None = None

    def child(self, *, agent_name: str | None = None, agent_type: str | None = None, parent_run_id: str | None = None) -> "OpsContext":
        return OpsContext(
            agent_name=agent_name or self.agent_name,
            agent_type=agent_type or self.agent_type,
            parent_run_id=parent_run_id if parent_run_id is not None else self.parent_run_id,
        )


def init_db(ctx: OpsContext, workspace: Path, migrations_dir: Path) -> Path:
    migrations_path = migrations_dir
    if not migrations_path.exists():
        repo_root = Path(__file__).resolve().parents[2]
        fallback = repo_root / "db" / "migrations"
        if fallback.exists():
            migrations_path = fallback
    orch = default_orchestrator()
    skill = InitWorkspaceSkill()
    result = skill.run(
        orch,
        workspace=workspace,
        migrations_dir=migrations_path,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )
    db_path = Path(result.get("db_path") or workspace / "index" / "agent.db")
    if migrations_path.exists():
        con = connect(db_path)
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'perf_spans'"
        ).fetchone()
        if row is None:
            apply_migrations_from_dir(con, migrations_path)
        con.close()
    return db_path


def list_runs(ctx: OpsContext, workspace: Path, limit: int = 50) -> list[dict[str, Any]]:
    orch = default_orchestrator()
    skill = ListRunsSkill()
    return skill.run(
        orch,
        workspace=workspace,
        limit=limit,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def list_skills(ctx: OpsContext, skills_dir: Path = Path("skills")) -> list[dict[str, str]]:
    orch = default_orchestrator()
    skill = ListSkillsSkill()
    return skill.run(
        orch,
        skills_dir=skills_dir,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def create_skill(
    ctx: OpsContext,
    skill_name: str,
    description: str,
    body: str,
    skills_dir: Path = Path("skills"),
) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{1,64}", skill_name):
        raise ValueError("skill_name must be lowercase letters, digits, or hyphens (max 64 chars)")
    orch = default_orchestrator()
    skill = CreateSkillSkill()
    result = skill.run(
        orch,
        skill_name=skill_name,
        description=description,
        body=body,
        skills_dir=skills_dir,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )
    return Path(result.get("path") or skills_dir / skill_name / "SKILL.md")


def load_run(ctx: OpsContext, workspace: Path, run_id_value: str) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = LoadRunSkill()
    return skill.run(
        orch,
        workspace=workspace,
        run_id=run_id_value,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def read_file(ctx: OpsContext, path: str) -> str:
    orch = default_orchestrator()
    skill = ReadFileSkill()
    return skill.run(
        orch,
        path=path,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def query_rows(
    ctx: OpsContext,
    sql: str,
    params: list[Any] | None = None,
    *,
    workspace: Path | None = None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    resolved_db_path = None
    if db_path is not None:
        resolved_db_path = str(db_path)
    elif workspace is not None:
        resolved_db_path = str(Path(workspace) / "index" / "agent.db")
    orch = default_orchestrator()
    skill = QueryRowsSkill()
    return skill.run(
        orch,
        sql=sql,
        params=params or [],
        db_path=resolved_db_path,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def validate_environment(
    ctx: OpsContext,
    *,
    workspace: Path,
    require_llm: bool,
    auto_start: bool = True,
    min_free_mb: int = 50,
) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = ValidateEnvironmentSkill()
    return skill.run(
        orch,
        db_path=str(Path(workspace) / "index" / "agent.db"),
        require_llm=require_llm,
        min_free_mb=min_free_mb,
        auto_start=auto_start,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def list_document_duplicates(ctx: OpsContext, workspace: Path) -> list[dict[str, Any]]:
    orch = default_orchestrator()
    skill = ListDocumentDuplicatesSkill()
    return skill.run(
        orch,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def delete_duplicate_documents(
    ctx: OpsContext,
    workspace: Path,
    doc_ids: list[str],
    *,
    delete_files: bool = True,
) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = DeleteDuplicateDocumentsSkill()
    return skill.run(
        orch,
        workspace=workspace,
        doc_ids=doc_ids,
        delete_files=delete_files,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def search_local(ctx: OpsContext, query: str, workspace: Path, limit: int = 20) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = SearchLocalSkill()
    return skill.run(
        orch,
        query=query,
        workspace=workspace,
        limit=limit,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def build_embeddings(
    ctx: OpsContext,
    workspace: Path,
    *,
    model_name: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 64,
    include_docs: bool = True,
    include_ideas: bool = True,
    log_fn=None,
) -> dict[str, int]:
    orch = default_orchestrator()
    skill = BuildEmbeddingsSkill()
    return skill.run(
        orch,
        workspace=workspace,
        model_name=model_name,
        batch_size=batch_size,
        include_docs=include_docs,
        include_ideas=include_ideas,
        log_fn=log_fn,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def search_semantic(
    ctx: OpsContext,
    query: str,
    workspace: Path,
    *,
    limit: int = 20,
    model_name: str = DEFAULT_EMBED_MODEL,
) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = SearchSemanticSkill()
    return skill.run(
        orch,
        query=query,
        workspace=workspace,
        limit=limit,
        model_name=model_name,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def embeddings_status(ctx: OpsContext, workspace: Path) -> dict[str, int]:
    orch = default_orchestrator()
    skill = EmbeddingsStatusSkill()
    return skill.run(
        orch,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def search_web(ctx: OpsContext, query: str, workspace: Path, top_n: int = 10) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = SearchWebSources()
    return skill.run(
        orch,
        query=query,
        top_n=top_n,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def fetch_run(
    ctx: OpsContext,
    run_id: str,
    workspace: Path,
    *,
    regenerate_summary: bool = False,
) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = FetchDocumentsFromRun()
    return skill.run(
        orch,
        run_id=run_id,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
        regenerate_summary=regenerate_summary,
    )


def fetch_urls(
    ctx: OpsContext,
    urls: list[str],
    workspace: Path,
    *,
    regenerate_summary: bool = False,
    prefer_chunking: bool = True,
    log_fn=None,
) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = FetchUrlsSkill()
    return skill.run(
        orch,
        urls=urls,
        workspace=workspace,
        regenerate_summary=regenerate_summary,
        prefer_chunking=prefer_chunking,
        log_fn=log_fn,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def fetch_and_index_urls(
    ctx: OpsContext,
    urls: list[str],
    workspace: Path,
    *,
    regenerate_summary: bool = False,
    prefer_chunking: bool = True,
    log_fn=None,
) -> dict[str, Any]:
    fetch_result = fetch_urls(
        ctx,
        urls,
        workspace,
        regenerate_summary=regenerate_summary,
        prefer_chunking=prefer_chunking,
        log_fn=log_fn,
    )
    created = fetch_result.get("created_docs", [])
    index_result = index_documents(ctx, created, workspace)
    return {
        **fetch_result,
        "indexed": index_result.get("indexed", 0),
        "index_failed": index_result.get("failed", 0),
    }


def resummarize_documents(
    ctx: OpsContext,
    workspace: Path,
    *,
    only_missing: bool = True,
    prefer_chunking: bool = True,
    limit: int | None = None,
    log_fn=None,
) -> dict[str, int]:
    orch = default_orchestrator()
    skill = ResummarizeDocumentsSkill()
    return skill.run(
        orch,
        workspace=workspace,
        only_missing=only_missing,
        prefer_chunking=prefer_chunking,
        limit=limit,
        log_fn=log_fn,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def index_docs(ctx: OpsContext, run_id: str, workspace: Path) -> int:
    orch = default_orchestrator()
    skill = IndexDocumentsFromRun()
    return skill.run(
        orch,
        run_id=run_id,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def summarize_docs(
    ctx: OpsContext,
    run_id: str,
    workspace: Path,
    *,
    prefer_chunking: bool = False,
    overwrite: bool = False,
) -> dict[str, int]:
    run = load_run(ctx, workspace, run_id)
    outputs = run.get("outputs") or {}
    doc_paths = outputs.get("documents_created", [])
    if not doc_paths:
        return {"summarized": 0, "skipped": 0, "failed": 0}
    return summarize_documents(
        ctx,
        doc_paths,
        workspace,
        prefer_chunking=prefer_chunking,
        overwrite=overwrite,
    )


def index_documents(ctx: OpsContext, doc_paths: list[str], workspace: Path) -> dict[str, int]:
    orch = default_orchestrator()
    skill = IndexDocumentsSkill()
    return skill.run(
        orch,
        doc_paths=doc_paths,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def create_idea(ctx: OpsContext, title: str, statement: str, proposed_by: str, workspace: Path) -> dict[str, str]:
    orch = default_orchestrator()
    skill = CreateIdeaSkill()
    return skill.run(
        orch,
        title=title,
        statement=statement,
        proposed_by=proposed_by,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def match_all_ideas(ctx: OpsContext, workspace: Path, top_n: int = 10, *, log_fn=None) -> int:
    orch = default_orchestrator()
    skill = MatchAllIdeasSkill()
    return skill.run(
        orch,
        workspace=workspace,
        top_n=top_n,
        log_fn=log_fn,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def match_all_docs(ctx: OpsContext, workspace: Path, top_n: int = 10, *, log_fn=None) -> int:
    orch = default_orchestrator()
    skill = MatchAllDocsSkill()
    return skill.run(
        orch,
        workspace=workspace,
        top_n=top_n,
        log_fn=log_fn,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def match_single_idea(ctx: OpsContext, idea_id: str, workspace: Path, top_n: int = 10) -> list[Any]:
    orch = default_orchestrator()
    skill = MatchSingleIdeaSkill()
    return skill.run(
        orch,
        workspace=workspace,
        idea_id=idea_id,
        top_n=top_n,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def match_single_doc(ctx: OpsContext, document_id: str, workspace: Path, top_n: int = 10) -> list[Any]:
    orch = default_orchestrator()
    skill = MatchSingleDocSkill()
    return skill.run(
        orch,
        workspace=workspace,
        document_id=document_id,
        top_n=top_n,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )

def summarize_documents(
    ctx: OpsContext,
    doc_paths: list[str],
    workspace: Path,
    *,
    prefer_chunking: bool = False,
    overwrite: bool = False,
    log_fn=None,
) -> dict[str, int]:
    orch = default_orchestrator()
    skill = SummarizeDocumentsSkill()
    return skill.run(
        orch,
        doc_paths=doc_paths,
        workspace=workspace,
        prefer_chunking=prefer_chunking,
        overwrite=overwrite,
        log_fn=log_fn,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )

def match_learning(
    ctx: OpsContext,
    workspace: Path,
    *,
    rules_path: Path | None = None,
    high_threshold: int = 8,
    low_threshold: int = 4,
) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = MatchLearningSkill()
    return skill.run(
        orch,
        workspace=workspace,
        rules_path=rules_path,
        high_threshold=high_threshold,
        low_threshold=low_threshold,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def judge_validity_report(ctx: OpsContext, workspace: Path) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = JudgeValiditySkill()
    return skill.run(
        orch,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def build_dashboard(ctx: OpsContext, workspace: Path) -> Path:
    orch = default_orchestrator()
    skill = BuildDashboardSkill()
    return skill.run(
        orch,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def plan_match(ctx: OpsContext, match_id: str, workspace: Path) -> str:
    orch = default_orchestrator()
    skill = PlanMatchSkill()
    return skill.run(
        orch,
        workspace=workspace,
        match_id=match_id,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def plan_backlog(ctx: OpsContext, workspace: Path) -> list[dict[str, Any]]:
    orch = default_orchestrator()
    skill = PlanBacklogSkill()
    return skill.run(
        orch,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def plan_update(ctx: OpsContext, task_id: str, status_val: str, workspace: Path) -> None:
    orch = default_orchestrator()
    skill = PlanUpdateSkill()
    skill.run(
        orch,
        workspace=workspace,
        task_id=task_id,
        status_val=status_val,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def plan_assign(ctx: OpsContext, task_id: str, agent: str, workspace: Path) -> None:
    orch = default_orchestrator()
    skill = PlanAssignSkill()
    skill.run(
        orch,
        workspace=workspace,
        task_id=task_id,
        agent=agent,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def cleanup_db(ctx: OpsContext, workspace: Path, dry_run: bool = True) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = CleanupDbSkill()
    return skill.run(
        orch,
        workspace=workspace,
        dry_run=dry_run,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def cleanup_content(ctx: OpsContext, workspace: Path, dry_run: bool = True) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = CleanupContentSkill()
    return skill.run(
        orch,
        workspace=workspace,
        dry_run=dry_run,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def delete_all_data(ctx: OpsContext, workspace: Path, *, delete_files: bool = True) -> dict[str, Any]:
    orch = default_orchestrator()
    skill = DeleteAllDataSkill()
    return skill.run(
        orch,
        workspace=workspace,
        delete_files=delete_files,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )


def demo_seed(ctx: OpsContext, workspace: Path, migrations_dir: Path) -> None:
    init_db(ctx, workspace, migrations_dir)
    orch = default_orchestrator()
    skill = DemoSeedSkill()
    skill.run(
        orch,
        workspace=workspace,
        agent_name=ctx.agent_name,
        agent_type=ctx.agent_type,
        parent_run_id=ctx.parent_run_id,
    )
