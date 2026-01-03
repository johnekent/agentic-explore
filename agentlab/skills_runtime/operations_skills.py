from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from agentlab.core.frontmatter import dump_md_with_frontmatter, parse_md_with_frontmatter
from agentlab.core.paths import utc_now_iso
from agentlab.pipeline.summarize import SYSTEM_SUMMARIZE
from agentlab.pipeline.web import extract_readable_text
from agentlab.skills_runtime.base import Skill, SkillSpec
from agentlab.skills_runtime.ops_helpers import emit_status, end_ops_run, log_item_processing, perf_span, start_ops_run, use_tool
from agentlab.skills_runtime.summarize_helpers import summarize_with_fallback


def _db_path(workspace: Path) -> str:
    return str(Path(workspace) / "index" / "agent.db")


def _dated_content_path(workspace: Path, kind: str, item_id: str, filename: str) -> Path:
    now = datetime.now()
    return (
        Path(workspace)
        / "content"
        / kind
        / now.strftime("%Y")
        / now.strftime("%m")
        / item_id
        / filename
    )


class InitWorkspace(Skill):
    spec = SkillSpec(name="init_workspace", required_capabilities=["cap.db_migrate", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        migrations_dir: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="init",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            result = use_tool(
                orch,
                capability="cap.db_migrate",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"workspace": str(workspace), "migrations_dir": str(migrations_dir)},
                workspace=str(workspace),
                migrations_dir=str(migrations_dir),
            )
            if not result.ok:
                raise RuntimeError(result.error)
            return {"db_path": result.data.get("db_path")}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class ListRuns(Skill):
    spec = SkillSpec(name="list_runs", required_capabilities=["cap.query_rows", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        limit: int = 50,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="runs-list",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            list_res = use_tool(
                orch,
                capability="cap.query_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                sql=(
                    "SELECT run_id, topic, started_at, ended_at, params_json, outputs_json "
                    "FROM runs ORDER BY started_at DESC LIMIT ?"
                ),
                params=[limit],
                db_path=_db_path(workspace),
            )
            if not list_res.ok:
                raise RuntimeError(list_res.error)
            runs = []
            for row in list_res.data.get("rows", []):
                params = row.get("params_json") or ""
                outputs = row.get("outputs_json") or ""
                runs.append(
                    {
                        "run_id": row.get("run_id"),
                        "topic": row.get("topic"),
                        "started_at": row.get("started_at"),
                        "ended_at": row.get("ended_at"),
                        "params": json.loads(params) if params else {},
                        "outputs": json.loads(outputs) if outputs else {},
                    }
                )
            return runs
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class LoadRun(Skill):
    spec = SkillSpec(name="load_run", required_capabilities=["cap.query_rows", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        run_id: str,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="runs-load",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            read_res = use_tool(
                orch,
                capability="cap.query_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                sql="SELECT run_id, topic, started_at, ended_at, params_json, outputs_json FROM runs WHERE run_id = ? LIMIT 1",
                params=[run_id],
                db_path=_db_path(workspace),
            )
            if not read_res.ok:
                raise RuntimeError(read_res.error)
            rows = read_res.data.get("rows", [])
            if not rows:
                raise ValueError("run not found for run_id")
            row = rows[0]
            params = row.get("params_json") or ""
            outputs = row.get("outputs_json") or ""
            return {
                "run_id": row.get("run_id"),
                "topic": row.get("topic"),
                "started_at": row.get("started_at"),
                "ended_at": row.get("ended_at"),
                "params": json.loads(params) if params else {},
                "outputs": json.loads(outputs) if outputs else {},
            }
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class ListSkills(Skill):
    spec = SkillSpec(name="list_skills", required_capabilities=["cap.file_list", "cap.file_read", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        skills_dir: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> list[dict[str, str]]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="skills-list",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            list_res = use_tool(
                orch,
                capability="cap.file_list",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"root": str(skills_dir), "pattern": "*/SKILL.md"},
                root=str(skills_dir),
                pattern="*/SKILL.md",
            )
            if not list_res.ok:
                raise RuntimeError(list_res.error)
            skills = []
            for path in sorted(list_res.data.get("files", [])):
                read_res = use_tool(
                    orch,
                    capability="cap.file_read",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"path": path},
                    path=path,
                )
                if not read_res.ok:
                    raise RuntimeError(read_res.error)
                md = parse_md_with_frontmatter(read_res.data.get("content") or "")
                name = str(md.frontmatter.get("name") or Path(path).parent.name)
                desc = str(md.frontmatter.get("description") or "")
                skills.append({"name": name, "description": desc, "path": path})
            return skills
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class CreateSkill(Skill):
    spec = SkillSpec(name="create_skill", required_capabilities=["cap.file_write", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        skill_name: str,
        description: str,
        body: str,
        skills_dir: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, str]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="skills-create",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            skill_path = Path(skills_dir) / skill_name / "SKILL.md"
            frontmatter = {"name": skill_name, "description": description}
            content = dump_md_with_frontmatter(frontmatter, body)
            write_res = use_tool(
                orch,
                capability="cap.file_write",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"path": str(skill_path)},
                path=str(skill_path),
                content=content,
            )
            if not write_res.ok:
                raise RuntimeError(write_res.error)
            return {"path": str(skill_path)}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class ReadFile(Skill):
    spec = SkillSpec(name="read_file", required_capabilities=["cap.file_read", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        path: str,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> str:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="file-read",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            read_res = use_tool(
                orch,
                capability="cap.file_read",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"path": path},
                path=path,
            )
            if not read_res.ok:
                raise RuntimeError(read_res.error)
            return str(read_res.data.get("content") or "")
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class QueryRows(Skill):
    spec = SkillSpec(name="query_rows", required_capabilities=["cap.query_rows", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        sql: str,
        params: list[Any] | None,
        db_path: str | None,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="query-rows",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.query_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"sql": sql},
                sql=sql,
                params=params or [],
                db_path=db_path,
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return res.data.get("rows", [])
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class ValidateEnvironment(Skill):
    spec = SkillSpec(
        name="validate_environment",
        required_capabilities=["cap.env_check_db", "cap.env_check_llm", "cap.ops_logging"],
    )

    def run(
        self,
        orch,
        *,
        db_path: str,
        require_llm: bool,
        min_free_mb: int = 50,
        auto_start: bool = True,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="env-validate",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            db_res = use_tool(
                orch,
                capability="cap.env_check_db",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"db_path": db_path, "min_free_mb": min_free_mb},
                db_path=db_path,
                min_free_mb=min_free_mb,
            )
            if not db_res.ok:
                raise RuntimeError(db_res.error)

            llm_res = use_tool(
                orch,
                capability="cap.env_check_llm",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"require_llm": require_llm, "auto_start": auto_start},
                timeout_s=2,
                auto_start=auto_start,
            )
            if not llm_res.ok:
                raise RuntimeError(llm_res.error)
            if require_llm and not llm_res.data.get("ready", False):
                raise RuntimeError({"code": "llm_unavailable", "message": "LLM provider not available."})
            return {"db": db_res.data, "llm": llm_res.data}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class SearchLocal(Skill):
    spec = SkillSpec(name="search_local", required_capabilities=["cap.query_rows", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        query: str,
        workspace: Path,
        limit: int = 20,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose=f"local-search:{query}",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            tokens = [t.lower() for t in re.split(r"\W+", query) if len(t) > 2]
            if not tokens:
                return {"documents": [], "ideas": []}

            def score_text(text: str) -> int:
                total = 0
                for t in tokens:
                    total += text.count(t)
                return total

            def fetch_rows(table: str, fields: list[str]) -> list[dict[str, Any]]:
                like_clauses = []
                params: list[str] = []
                for t in tokens:
                    like_clauses.append("(title LIKE ? OR summary LIKE ? OR source_text LIKE ?)")
                    term = f"%{t}%"
                    params.extend([term, term, term])
                sql = f"SELECT {', '.join(fields)} FROM {table} WHERE " + " OR ".join(like_clauses)
                res = use_tool(
                    orch,
                    capability="cap.query_rows",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"table": table, "query": query},
                    sql=sql,
                    params=params,
                    db_path=_db_path(workspace),
                )
                if not res.ok:
                    raise RuntimeError(res.error)
                return res.data.get("rows", [])

            doc_fields = ["id", "title", "summary", "source_text", "url", "retrieved_at"]
            idea_fields = ["id", "title", "summary", "source_text", "proposed_by", "created_at"]
            docs = fetch_rows("documents", doc_fields)
            ideas = fetch_rows("ideas", idea_fields)

            def rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
                scored = []
                for r in rows:
                    blob = " ".join(
                        [
                            str(r.get("title") or ""),
                            str(r.get("summary") or ""),
                            str(r.get("source_text") or ""),
                        ]
                    ).lower()
                    scored.append({**r, "score": score_text(blob)})
                scored.sort(key=lambda x: x["score"], reverse=True)
                return scored[:max(1, limit)]

            return {"documents": rank(docs), "ideas": rank(ideas)}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class BuildEmbeddings(Skill):
    spec = SkillSpec(
        name="embeddings_build",
        required_capabilities=["cap.vector_index", "cap.query_rows", "cap.persistence", "cap.env_check_db", "cap.ops_logging"],
    )

    def run(
        self,
        orch,
        *,
        workspace: Path,
        model_name: str,
        batch_size: int,
        include_docs: bool,
        include_ideas: bool,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
        log_fn=None,
    ) -> dict[str, int]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="embeddings-build",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            if log_fn:
                log_fn(f"[embed] start model={model_name} batch_size={batch_size}")
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message=f"Embedding start model={model_name} batch_size={batch_size}",
                stage="start",
                log_fn=log_fn,
            )
            env_skill = ValidateEnvironment()
            env_skill.run(
                orch,
                db_path=_db_path(workspace),
                require_llm=False,
                agent_name=agent_name,
                agent_type=agent_type,
                parent_run_id=ops_run_id,
            )
            with perf_span(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                span_name="vector_index",
                category="embedding",
                metadata={
                    "model_name": model_name,
                    "batch_size": batch_size,
                    "include_docs": include_docs,
                    "include_ideas": include_ideas,
                },
            ):
                res = use_tool(
                    orch,
                    capability="cap.vector_index",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={
                        "model_name": model_name,
                        "batch_size": batch_size,
                        "include_docs": include_docs,
                        "include_ideas": include_ideas,
                    },
                    db_path=_db_path(workspace),
                    model_name=model_name,
                    batch_size=batch_size,
                    include_docs=include_docs,
                    include_ideas=include_ideas,
                )
            if not res.ok:
                raise RuntimeError(res.error)
            if include_docs:
                rows_res = use_tool(
                    orch,
                    capability="cap.query_rows",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    sql="SELECT id FROM documents",
                    params=[],
                    db_path=_db_path(workspace),
                )
                if not rows_res.ok:
                    raise RuntimeError(rows_res.error)
                for row in rows_res.data.get("rows", []):
                    log_item_processing(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        item_type="document", item_id=str(row.get("id") or ""),
                        stage="embed",
                        status="success",
                        db_path=_db_path(workspace),
                        metadata={"model": model_name},
                    )
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message=f"Embedding complete docs={res.data.get('documents')} ideas={res.data.get('ideas')}",
                stage="complete",
                log_fn=log_fn,
            )
            return {"documents": int(res.data.get("documents", 0)), "ideas": int(res.data.get("ideas", 0))}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class EmbeddingsStatus(Skill):
    spec = SkillSpec(name="embeddings_status", required_capabilities=["cap.vector_stats", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, int]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="embeddings-status",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.vector_stats",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                db_path=_db_path(workspace),
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return {"documents": int(res.data.get("documents", 0)), "ideas": int(res.data.get("ideas", 0))}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class SearchSemantic(Skill):
    spec = SkillSpec(
        name="search_semantic",
        required_capabilities=["cap.vector_query", "cap.query_rows", "cap.env_check_db", "cap.ops_logging"],
    )

    def run(
        self,
        orch,
        *,
        query: str,
        workspace: Path,
        limit: int,
        model_name: str,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose=f"semantic-search:{query}",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            env_skill = ValidateEnvironment()
            env_skill.run(
                orch,
                db_path=_db_path(workspace),
                require_llm=False,
                agent_name=agent_name,
                agent_type=agent_type,
                parent_run_id=ops_run_id,
            )
            res = use_tool(
                orch,
                capability="cap.vector_query",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"query": query, "limit": limit, "model_name": model_name},
                db_path=_db_path(workspace),
                query=query,
                limit=limit,
                model_name=model_name,
            )
            if not res.ok:
                raise RuntimeError(res.error)
            doc_hits = res.data.get("documents", [])
            idea_hits = res.data.get("ideas", [])
            doc_ids = [r.get("doc_id") for r in doc_hits if r.get("doc_id")]
            idea_ids = [r.get("idea_id") for r in idea_hits if r.get("idea_id")]

            def hydrate(table: str, fields: list[str], ids: list[str], id_field: str) -> dict[str, dict[str, Any]]:
                if not ids:
                    return {}
                placeholders = ",".join("?" * len(ids))
                sql = f"SELECT {', '.join(fields)} FROM {table} WHERE {id_field} IN ({placeholders})"
                rows_res = use_tool(
                    orch,
                    capability="cap.query_rows",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    sql=sql,
                    params=ids,
                    db_path=_db_path(workspace),
                )
                if not rows_res.ok:
                    raise RuntimeError(rows_res.error)
                rows = rows_res.data.get("rows", [])
                return {str(r[id_field]): r for r in rows}

            doc_fields = ["id", "title", "summary", "url", "retrieved_at"]
            idea_fields = ["id", "title", "summary", "proposed_by", "created_at"]
            docs_map = hydrate("documents", doc_fields, doc_ids, "id")
            ideas_map = hydrate("ideas", idea_fields, idea_ids, "id")
            docs = [{**docs_map.get(r.get("doc_id"), {"id": r.get("doc_id")}), "distance": r.get("distance")} for r in doc_hits]
            ideas = [{**ideas_map.get(r.get("idea_id"), {"id": r.get("idea_id")}), "distance": r.get("distance")} for r in idea_hits]
            return {"documents": docs, "ideas": ideas}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)

class FetchUrls(Skill):
    spec = SkillSpec(
        name="fetch_urls",
        required_capabilities=[
            "cap.query_rows",
            "cap.http_fetch",
            "cap.file_write",
            "cap.llm_generate",
            "cap.env_check_db",
            "cap.env_check_llm",
            "cap.ops_logging",
        ],
    )

    def run(
        self,
        orch,
        *,
        urls: list[str],
        workspace: Path,
        regenerate_summary: bool,
        prefer_chunking: bool = True,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
        log_fn=None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="fetch-index",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        fetched = 0
        skipped = 0
        failed: list[str] = []
        created: list[str] = []
        try:
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message=f"Fetch start urls={len(urls)}",
                stage="start",
                log_fn=log_fn,
            )
            env_skill = ValidateEnvironment()
            env_skill.run(
                orch,
                db_path=_db_path(workspace),
                require_llm=True,
                auto_start=True,
                agent_name=agent_name,
                agent_type=agent_type,
                parent_run_id=ops_run_id,
            )
            for url in urls:
                emit_status(
                    orch,
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    message=f"Fetching {url}",
                    stage="fetch",
                    log_fn=log_fn,
                )
                span_meta = {"url": url}
                with perf_span(
                    orch,
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    span_name="fetch_document",
                    category="item",
                    metadata=span_meta,
                ):
                    dup_res = use_tool(
                        orch,
                        capability="cap.query_rows",
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        parameters={"url": url},
                        sql="SELECT id FROM documents WHERE url = ? LIMIT 1",
                        params=[url],
                        db_path=_db_path(workspace),
                    )
                    if not dup_res.ok:
                        raise RuntimeError(dup_res.error)
                    if dup_res.data.get("rows"):
                        doc_id = str(dup_res.data["rows"][0].get("id"))
                        span_meta["doc_id"] = doc_id
                        log_item_processing(
                            orch,
                            run_id=ops_run_id,
                            skill_name=self.spec.name,
                            item_type="document", item_id=doc_id,
                            stage="fetch",
                            status="skipped_duplicate",
                            db_path=_db_path(workspace),
                            metadata={"url": url},
                        )
                        skipped += 1
                        continue
                    fetch_res = use_tool(
                        orch,
                        capability="cap.http_fetch",
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        parameters={"url": url},
                        url=url,
                        timeout_s=30,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    if not fetch_res.ok:
                        failed.append(f"{url}: {fetch_res.error}")
                        log_item_processing(
                            orch,
                            run_id=ops_run_id,
                            skill_name=self.spec.name,
                            item_type="document",
                            item_id=str(uuid.uuid4()),
                            stage="fetch",
                            status="failed",
                            db_path=_db_path(workspace),
                            error=str(fetch_res.error),
                            metadata={"url": url},
                        )
                        continue
                    text = extract_readable_text(fetch_res.data.get("text") or "")
                    doc_id = str(uuid.uuid4())
                    span_meta["doc_id"] = doc_id
                    title = ""
                    summary = ""
                    summary_attempted = False
                    if regenerate_summary or not (title and summary):
                        summary_attempted = True
                        prompt = text[:6000]
                        prompt = f"URL: {url}\n\nCONTENT:\n{prompt}"
                        llm_out = summarize_with_fallback(
                            orch,
                            run_id=ops_run_id,
                            skill_name=self.spec.name,
                            system=SYSTEM_SUMMARIZE,
                            prompt=prompt,
                            text=text,
                            doc_id=doc_id,
                            prefer_chunking=prefer_chunking,
                            log_fn=log_fn,
                        )
                        title = llm_out.get("title") or title
                        summary = llm_out.get("summary") or summary
                    doc_path = _dated_content_path(workspace, "documents", doc_id, "doc.md")
                    fm = {
                        "id": doc_id,
                        "type": "document",
                        "title": title,
                        "url": url,
                        "retrieved_at": utc_now_iso(),
                        "run_id": None,
                        "summary": summary,
                        "asset_type": "url",
                        "asset_ref": url,
                        "asset_path": None,
                        "tags": [],
                        "taxonomies": {"domain": [], "use_case": [], "risk": [], "maturity": []},
                        "source": f"UI fetch: {url}",
                        "review": {"score": None, "notes": ""},
                    }
                    content = dump_md_with_frontmatter(fm, f"# Content\n\n{text[:20000]}\n")
                    write_res = use_tool(
                        orch,
                        capability="cap.file_write",
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        parameters={"path": str(doc_path)},
                        path=str(doc_path),
                        content=content,
                    )
                    if not write_res.ok:
                        failed.append(f"{url}: {write_res.error}")
                        log_item_processing(
                            orch,
                            run_id=ops_run_id,
                            skill_name=self.spec.name,
                            item_type="document",
                            item_id=doc_id,
                            stage="fetch",
                            status="failed",
                            db_path=_db_path(workspace),
                            error=str(write_res.error),
                            metadata={"url": url, "path": str(doc_path)},
                        )
                        continue
                    log_item_processing(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        item_type="document", item_id=doc_id,
                        stage="fetch",
                        status="success",
                        db_path=_db_path(workspace),
                        metadata={"url": url, "path": str(doc_path)},
                    )
                    if summary_attempted:
                        log_item_processing(
                            orch,
                            run_id=ops_run_id,
                            skill_name=self.spec.name,
                            item_type="document", item_id=doc_id,
                            stage="summary",
                            status="success",
                            db_path=_db_path(workspace),
                        )
                    created.append(str(doc_path))
                    fetched += 1
                if fetched % 5 == 0:
                    emit_status(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        message=f"Fetch progress fetched={fetched} skipped={skipped} failed={len(failed)}",
                        stage="progress",
                        log_fn=log_fn,
                    )
            if failed:
                status = "error"
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message=f"Fetch complete fetched={fetched} skipped={skipped} failed={len(failed)}",
                stage="complete",
                log_fn=log_fn,
            )
            return {"fetched": fetched, "failed_urls": failed, "skipped": skipped, "created_docs": created}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class IndexDocuments(Skill):
    spec = SkillSpec(
        name="index_documents",
        required_capabilities=["cap.index_document", "cap.ops_logging"],
    )

    def run(
        self,
        orch,
        *,
        doc_paths: list[str],
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, int]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="index-documents",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        indexed = 0
        failed = 0

        def _doc_id_from_path(path: Path) -> str | None:
            try:
                fm, _ = parse_md_with_frontmatter(path.read_text(encoding="utf-8"))
                return str(fm.get("id") or "").strip() or None
            except Exception:
                return None

        try:
            for path_str in doc_paths:
                path = Path(path_str)
                fallback_id = _doc_id_from_path(path) or str(uuid.uuid4())
                res = use_tool(
                    orch,
                    capability="cap.index_document",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"path": str(path)},
                    doc_path=str(path),
                )
                if res.ok:
                    indexed += 1
                    doc_id = str(res.data.get("id") or fallback_id)
                    log_item_processing(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        item_type="document", item_id=doc_id,
                        stage="index",
                        status="success",
                        db_path=_db_path(workspace),
                        metadata={"path": str(path)},
                    )
                else:
                    failed += 1
                    log_item_processing(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        item_type="document", item_id=fallback_id,
                        stage="index",
                        status="failed",
                        db_path=_db_path(workspace),
                        error=str(res.error),
                        metadata={"path": str(path)},
                    )
            return {"indexed": indexed, "failed": failed}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class ResummarizeDocuments(Skill):
    spec = SkillSpec(
        name="resummarize_documents",
        required_capabilities=[
            "cap.query_rows",
            "cap.file_read",
            "cap.llm_generate",
            "cap.update_rows",
            "cap.persistence",
            "cap.env_check_db",
            "cap.env_check_llm",
            "cap.ops_logging",
        ],
    )

    def run(
        self,
        orch,
        *,
        workspace: Path,
        only_missing: bool,
        prefer_chunking: bool = True,
        limit: int | None,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
        log_fn=None,
    ) -> dict[str, int]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="resummarize-docs",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        updated = 0
        errors = 0
        processed = 0
        try:
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message="Resummarize start",
                stage="start",
                log_fn=log_fn,
            )
            env_skill = ValidateEnvironment()
            env_skill.run(
                orch,
                db_path=_db_path(workspace),
                require_llm=True,
                auto_start=True,
                agent_name=agent_name,
                agent_type=agent_type,
                parent_run_id=ops_run_id,
            )
            rows_res = use_tool(
                orch,
                capability="cap.query_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                sql="SELECT id, url, content_path, title, summary FROM documents",
                params=[],
                db_path=_db_path(workspace),
            )
            if not rows_res.ok:
                raise RuntimeError(rows_res.error)
            rows = rows_res.data.get("rows", [])
            if limit is not None:
                rows = rows[:limit]
            for r in rows:
                title = str(r.get("title") or "")
                summary = str(r.get("summary") or "")
                if only_missing and title and summary:
                    continue
                path = Path(r.get("content_path") or "")
                read_res = use_tool(
                    orch,
                    capability="cap.file_read",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"path": str(path)},
                    path=str(path),
                )
                if not read_res.ok:
                    if log_fn:
                        log_fn(f"[resum] skip missing file id={r.get('id')}")
                    continue
                md = parse_md_with_frontmatter(read_res.data.get("content") or "")
                text = md.body.strip() or read_res.data.get("content") or ""
                processed += 1
                try:
                    prompt = text[:6000]
                    url = r.get("url")
                    if url:
                        prompt = f"URL: {url}\n\nCONTENT:\n{prompt}"
                    llm_out = summarize_with_fallback(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        system=SYSTEM_SUMMARIZE,
                        prompt=prompt,
                        text=text,
                        doc_id=str(r.get("id") or ""),
                        prefer_chunking=prefer_chunking,
                        log_fn=log_fn,
                    )
                    new_title = llm_out.get("title") or title
                    new_summary = llm_out.get("summary") or summary
                    if new_title != title or new_summary != summary:
                        upd_res = use_tool(
                            orch,
                            capability="cap.update_rows",
                            run_id=ops_run_id,
                            skill_name=self.spec.name,
                            parameters={"id": r.get("id")},
                            sql="UPDATE documents SET title = ?, summary = ? WHERE id = ?",
                            params=[new_title, new_summary, r.get("id")],
                            db_path=_db_path(workspace),
                        )
                        if not upd_res.ok:
                            raise RuntimeError(upd_res.error)
                        updated += 1
                    log_item_processing(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        item_type="document", item_id=str(r.get("id") or ""),
                        stage="summary",
                        status="success",
                        db_path=_db_path(workspace),
                    )
                except Exception as exc:
                    errors += 1
                    if log_fn:
                        log_fn(f"[resum] error id={r.get('id')} err={exc}")
                    log_item_processing(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        item_type="document", item_id=str(r.get("id") or ""),
                        stage="summary",
                        status="failed",
                        db_path=_db_path(workspace),
                        error=str(exc),
                    )
                if processed % 10 == 0 and processed > 0:
                    emit_status(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        message=f"Resummarize progress processed={processed} updated={updated} errors={errors}",
                        stage="progress",
                        log_fn=log_fn,
                    )
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message=f"Resummarize complete processed={processed} updated={updated} errors={errors}",
                stage="complete",
                log_fn=log_fn,
            )
            return {"processed": processed, "updated": updated, "errors": errors}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)

class CreateIdea(Skill):
    spec = SkillSpec(name="create_idea", required_capabilities=["cap.file_write", "cap.index_idea", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        title: str,
        statement: str,
        proposed_by: str,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, str]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="idea-create",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            iid = str(uuid.uuid4())
            idea_path = _dated_content_path(workspace, "ideas", iid, "idea.md")
            fm = {
                "id": iid,
                "type": "idea",
                "title": title,
                "created_at": utc_now_iso(),
                "status": "",
                "proposed_by": proposed_by,
                "tags": [],
                "taxonomies": {"domain": [], "use_case": [], "risk": [], "maturity": []},
                "desired_outcome": "",
                "source": f"Proposed by {proposed_by} via {agent_type}",
                "review": {"score": None, "notes": ""},
            }
            content = dump_md_with_frontmatter(fm, f"# Statement\n{statement}\n")
            write_res = use_tool(
                orch,
                capability="cap.file_write",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"path": str(idea_path)},
                path=str(idea_path),
                content=content,
            )
            if not write_res.ok:
                raise RuntimeError(write_res.error)
            index_res = use_tool(
                orch,
                capability="cap.index_idea",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"path": str(idea_path)},
                idea_path=str(idea_path),
            )
            if not index_res.ok:
                raise RuntimeError(index_res.error)
            return {"id": iid, "path": str(idea_path)}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class MatchAllIdeas(Skill):
    spec = SkillSpec(name="match_all_ideas", required_capabilities=["cap.query_rows", "cap.match_idea_to_docs", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        top_n: int,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
        log_fn=None,
    ) -> int:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="match-ideas",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message="Match ideas start",
                stage="start",
                log_fn=log_fn,
            )
            ids_res = use_tool(
                orch,
                capability="cap.query_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                sql="SELECT id FROM ideas",
                params=[],
                db_path=_db_path(workspace),
            )
            if not ids_res.ok:
                raise RuntimeError(ids_res.error)
            ids = [r["id"] for r in ids_res.data.get("rows", [])]
            for idx, iid in enumerate(ids, start=1):
                match_res = use_tool(
                    orch,
                    capability="cap.match_idea_to_docs",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"idea_id": iid, "top_n": top_n},
                    idea_id=iid,
                    top_n=top_n,
                    db_path=_db_path(workspace),
                )
                if not match_res.ok:
                    raise RuntimeError(match_res.error)
                if idx % 5 == 0:
                    emit_status(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        message=f"Match ideas progress {idx}/{len(ids)}",
                        stage="progress",
                        log_fn=log_fn,
                    )
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message=f"Match ideas complete total={len(ids)}",
                stage="complete",
                log_fn=log_fn,
            )
            return len(ids)
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class MatchAllDocs(Skill):
    spec = SkillSpec(name="match_all_docs", required_capabilities=["cap.query_rows", "cap.match_doc_to_ideas", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        top_n: int,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
        log_fn=None,
    ) -> int:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="match-docs",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message="Match docs start",
                stage="start",
                log_fn=log_fn,
            )
            ids_res = use_tool(
                orch,
                capability="cap.query_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                sql="SELECT id FROM documents",
                params=[],
                db_path=_db_path(workspace),
            )
            if not ids_res.ok:
                raise RuntimeError(ids_res.error)
            ids = [r["id"] for r in ids_res.data.get("rows", [])]
            for idx, did in enumerate(ids, start=1):
                match_res = use_tool(
                    orch,
                    capability="cap.match_doc_to_ideas",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"document_id": did, "top_n": top_n},
                    item_id=did,
                    top_n=top_n,
                    db_path=_db_path(workspace),
                )
                if not match_res.ok:
                    raise RuntimeError(match_res.error)
                if idx % 5 == 0:
                    emit_status(
                        orch,
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        message=f"Match docs progress {idx}/{len(ids)}",
                        stage="progress",
                        log_fn=log_fn,
                    )
            emit_status(
                orch,
                run_id=ops_run_id,
                skill_name=self.spec.name,
                message=f"Match docs complete total={len(ids)}",
                stage="complete",
                log_fn=log_fn,
            )
            return len(ids)
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class MatchSingleIdea(Skill):
    spec = SkillSpec(name="match_single_idea", required_capabilities=["cap.match_idea_to_docs", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        idea_id: str,
        top_n: int,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> list[Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="match-idea",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            match_res = use_tool(
                orch,
                capability="cap.match_idea_to_docs",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"idea_id": idea_id, "top_n": top_n},
                idea_id=idea_id,
                top_n=top_n,
                db_path=_db_path(workspace),
            )
            if not match_res.ok:
                raise RuntimeError(match_res.error)
            return match_res.data.get("matches", [])
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class MatchSingleDoc(Skill):
    spec = SkillSpec(name="match_single_doc", required_capabilities=["cap.match_doc_to_ideas", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        document_id: str,
        top_n: int,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> list[Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="match-doc",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            match_res = use_tool(
                orch,
                capability="cap.match_doc_to_ideas",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"document_id": document_id, "top_n": top_n},
                item_id=document_id,
                top_n=top_n,
                db_path=_db_path(workspace),
            )
            if not match_res.ok:
                raise RuntimeError(match_res.error)
            return match_res.data.get("matches", [])
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)

class JudgeValidity(Skill):
    spec = SkillSpec(name="judge_validity", required_capabilities=["cap.judge_validity", "cap.file_write", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="judge-validity",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.judge_validity",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                db_path=_db_path(workspace),
            )
            if not res.ok:
                raise RuntimeError(res.error)
            report = res.data.get("report", {})
            out_path = Path(workspace) / "exports" / "validity_failures.json"
            write_res = use_tool(
                orch,
                capability="cap.file_write",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"path": str(out_path)},
                path=str(out_path),
                content=json.dumps(report, indent=2),
            )
            if not write_res.ok:
                raise RuntimeError(write_res.error)
            return {"path": str(out_path), "report": report}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class BuildDashboard(Skill):
    spec = SkillSpec(name="build_dashboard", required_capabilities=["cap.build_dashboard", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> Path:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="dashboard-build",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            out_path = Path(workspace) / "exports" / "dashboard.md"
            res = use_tool(
                orch,
                capability="cap.build_dashboard",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"output_path": str(out_path)},
                db_path=_db_path(workspace),
                output_path=str(out_path),
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return out_path
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class PlanMatch(Skill):
    spec = SkillSpec(name="plan_match_execution", required_capabilities=["cap.plan_match_execution", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        match_id: str,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> str:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="plan-match",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.plan_match_execution",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"match_id": match_id},
                workspace=str(workspace),
                match_id=match_id,
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return str(res.data.get("task_id"))
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class PlanBacklog(Skill):
    spec = SkillSpec(name="plan_backlog", required_capabilities=["cap.plan_backlog", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="plan-backlog",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.plan_backlog",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                workspace=str(workspace),
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return res.data.get("tasks", [])
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class PlanUpdate(Skill):
    spec = SkillSpec(name="plan_update_status", required_capabilities=["cap.plan_update_status", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        task_id: str,
        status_val: str,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> None:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="plan-update-status",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.plan_update_status",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"task_id": task_id, "status": status_val},
                workspace=str(workspace),
                task_id=task_id,
                status=status_val,
            )
            if not res.ok:
                raise RuntimeError(res.error)
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class PlanAssign(Skill):
    spec = SkillSpec(name="plan_assign_agent", required_capabilities=["cap.plan_assign_agent", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        task_id: str,
        agent: str,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> None:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="plan-assign",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.plan_assign_agent",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"task_id": task_id, "agent": agent},
                workspace=str(workspace),
                task_id=task_id,
                agent=agent,
            )
            if not res.ok:
                raise RuntimeError(res.error)
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class CleanupDb(Skill):
    spec = SkillSpec(name="cleanup_db", required_capabilities=["cap.cleanup_db", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        dry_run: bool,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="cleanup-db",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.cleanup_db",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"dry_run": dry_run},
                workspace=str(workspace),
                dry_run=dry_run,
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return res.data or {}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class CleanupContent(Skill):
    spec = SkillSpec(name="cleanup_content", required_capabilities=["cap.cleanup_content", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        dry_run: bool,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="cleanup-content",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.cleanup_content",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"dry_run": dry_run},
                workspace=str(workspace),
                dry_run=dry_run,
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return res.data or {}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class DeleteAllData(Skill):
    spec = SkillSpec(name="delete_all_data", required_capabilities=["cap.delete_all_data", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        delete_files: bool = True,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="delete-all-data",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.delete_all_data",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                workspace=str(workspace),
                delete_files=delete_files,
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return res.data or {}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class ListDocumentDuplicates(Skill):
    spec = SkillSpec(name="list_document_duplicates", required_capabilities=["cap.list_document_duplicates", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="dedup-list",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.list_document_duplicates",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                db_path=_db_path(workspace),
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return res.data.get("groups", [])
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class DeleteDuplicateDocuments(Skill):
    spec = SkillSpec(name="delete_duplicate_documents", required_capabilities=["cap.delete_duplicate_documents", "cap.ops_logging"])

    def run(
        self,
        orch,
        *,
        workspace: Path,
        doc_ids: list[str],
        delete_files: bool,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="dedup-delete",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            res = use_tool(
                orch,
                capability="cap.delete_duplicate_documents",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"doc_ids": doc_ids, "delete_files": delete_files},
                db_path=_db_path(workspace),
                doc_ids=doc_ids,
                delete_files=delete_files,
            )
            if not res.ok:
                raise RuntimeError(res.error)
            return res.data or {}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class DemoSeed(Skill):
    spec = SkillSpec(
        name="demo_seed",
        required_capabilities=["cap.persist_rows", "cap.file_write", "cap.index_document", "cap.index_idea", "cap.ops_logging"],
    )

    def run(
        self,
        orch,
        *,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> None:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose="demo-seed",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            run_row = {
                "run_id": "demo",
                "topic": "demo seed",
                "started_at": utc_now_iso(),
                "ended_at": utc_now_iso(),
                "params_json": "{}",
                "outputs_json": "{}",
            }
            use_tool(
                orch,
                capability="cap.persist_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"table": "runs", "mode": "ignore"},
                table="runs",
                rows=[run_row],
                mode="ignore",
                db_path=_db_path(workspace),
            )
            ideas = [
                (
                    "Asset tokenization - operational model",
                    "Define a token lifecycle for real-world assets aligned with market infrastructure and compliance.",
                ),
                (
                    "Generative AI - evals & governance",
                    "Establish an eval+observability program for GenAI agents (safety, cost, accuracy) and an operating model.",
                ),
                (
                    "Quantum optimization - realistic use cases",
                    "Assess where quantum (QAOA/annealing) could augment portfolio/risk optimization; benchmark vs classical baselines.",
                ),
            ]
            for title, stmt in ideas:
                iid = str(uuid.uuid4())
                idea_path = _dated_content_path(workspace, "ideas", iid, "idea.md")
                fm = {
                    "id": iid,
                    "type": "idea",
                    "title": title,
                    "created_at": utc_now_iso(),
                    "status": "",
                    "proposed_by": "team",
                    "tags": [],
                    "taxonomies": {"domain": [], "use_case": [], "risk": [], "maturity": []},
                    "desired_outcome": "",
                    "source": "Synthetic demo idea",
                    "review": {"score": None, "notes": ""},
                }
                content = dump_md_with_frontmatter(fm, f"# Statement\n{stmt}\n")
                write_res = use_tool(
                    orch,
                    capability="cap.file_write",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"path": str(idea_path)},
                    path=str(idea_path),
                    content=content,
                )
                if not write_res.ok:
                    raise RuntimeError(write_res.error)
                index_res = use_tool(
                    orch,
                    capability="cap.index_idea",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"path": str(idea_path)},
                    idea_path=str(idea_path),
                )
                if not index_res.ok:
                    raise RuntimeError(index_res.error)

            docs = [
                (
                    "Tokenization primer (market infrastructure)",
                    "https://example.com/tokenization-primer",
                    "Lifecycle: issuance, custody, transfer, redemption. Settlement finality, registry design, and compliance controls.",
                ),
                (
                    "GenAI evals & observability playbook",
                    "https://example.com/genai-evals",
                    "Eval suite (accuracy, safety, cost), telemetry, red-teaming, and human-in-the-loop review for agentic workflows.",
                ),
                (
                    "Quantum optimization reality check",
                    "https://example.com/quantum-optimization",
                    "Maps optimization problems to QAOA/annealing, notes NISQ limits, and emphasizes benchmarking vs classical heuristics.",
                ),
            ]
            for title, url, summary in docs:
                doc_id = str(uuid.uuid4())
                doc_path = _dated_content_path(workspace, "documents", doc_id, "doc.md")
                fm = {
                    "id": doc_id,
                    "type": "document",
                    "title": title,
                    "url": url,
                    "retrieved_at": utc_now_iso(),
                    "run_id": "demo",
                    "summary": summary,
                    "tags": [],
                    "taxonomies": {"domain": [], "use_case": [], "risk": [], "maturity": []},
                    "source": f"Synthetic demo document: {title}",
                    "review": {"score": 8, "notes": "demo seed"},
                }
                content = dump_md_with_frontmatter(fm, f"# Content\n\n{summary}\n")
                write_res = use_tool(
                    orch,
                    capability="cap.file_write",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"path": str(doc_path)},
                    path=str(doc_path),
                    content=content,
                )
                if not write_res.ok:
                    raise RuntimeError(write_res.error)
                index_res = use_tool(
                    orch,
                    capability="cap.index_document",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"path": str(doc_path)},
                    doc_path=str(doc_path),
                )
                if not index_res.ok:
                    raise RuntimeError(index_res.error)
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)
