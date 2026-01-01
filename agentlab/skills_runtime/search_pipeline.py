from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agentlab.core.frontmatter import dump_md_with_frontmatter
from agentlab.core.paths import utc_now_iso
from agentlab.pipeline.summarize import SYSTEM_SUMMARIZE
from agentlab.pipeline.web import SearchHit, extract_readable_text
from agentlab.skills_runtime.base import Skill, SkillSpec
from agentlab.skills_runtime.ops_helpers import end_ops_run, start_ops_run, use_tool


class SearchWebSources(Skill):
    spec = SkillSpec(
        name="search_web_sources",
        required_capabilities=["cap.web_search", "cap.persistence", "cap.ops_logging"],
    )

    def run(
        self,
        orch,
        *,
        query: str,
        top_n: int = 10,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose=f"search:{query}",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            search_res = use_tool(
                orch,
                capability="cap.web_search",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"query": query, "top_n": top_n},
                query=query,
                top_n=top_n,
            )
            if not search_res.ok:
                raise RuntimeError(search_res.error)
            hits = [SearchHit(**h) for h in search_res.data.get("results", [])]
            search_run_id = str(uuid.uuid4())
            run = {
                "run_id": search_run_id,
                "topic": query,
                "started_at": utc_now_iso(),
                "ended_at": "",
                "outputs": {"candidates": [h.__dict__ for h in hits], "documents_created": []},
            }
            write_res = use_tool(
                orch,
                capability="cap.persistence",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"table": "runs", "mode": "insert"},
                table="runs",
                rows=[
                    {
                        "run_id": run["run_id"],
                        "topic": run["topic"],
                        "started_at": run["started_at"],
                        "ended_at": run["ended_at"],
                        "params_json": json.dumps({"query": query, "top_n": top_n}),
                        "outputs_json": json.dumps(run["outputs"]),
                    }
                ],
                mode="insert",
                db_path=str(Path(workspace) / "index" / "agent.db"),
            )
            if not write_res.ok:
                raise RuntimeError(write_res.error)
            return {"run_id": search_run_id, "hits": hits}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


def _parse_summary_json(text: str) -> dict[str, str]:
    data = json.loads(text)
    title = str(data.get("title") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if title or summary:
        return {"title": title, "summary": summary}
    raise ValueError("Empty summary payload.")


class FetchDocumentsFromRun(Skill):
    spec = SkillSpec(
        name="fetch_documents_from_run",
        required_capabilities=[
            "cap.file_write",
            "cap.http_fetch",
            "cap.query_rows",
            "cap.llm_generate",
            "cap.env_check_db",
            "cap.env_check_llm",
            "cap.update_rows",
            "cap.ops_logging",
        ],
    )

    def run(
        self,
        orch,
        *,
        run_id: str,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
        regenerate_summary: bool = False,
    ) -> dict[str, Any]:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose=f"fetch:{run_id}",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        created: list[str] = []
        skipped = 0
        try:
            env_db = use_tool(
                orch,
                capability="cap.env_check_db",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={"db_path": str(Path(workspace) / "index" / "agent.db")},
                db_path=str(Path(workspace) / "index" / "agent.db"),
                min_free_mb=50,
            )
            if not env_db.ok:
                raise RuntimeError(env_db.error)
            env_llm = use_tool(
                orch,
                capability="cap.env_check_llm",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                parameters={},
                timeout_s=2,
            )
            if not env_llm.ok:
                raise RuntimeError(env_llm.error)
            if regenerate_summary and not env_llm.data.get("ready", False):
                raise RuntimeError({"code": "llm_unavailable", "message": "LLM provider not available."})
            read_res = use_tool(
                orch,
                capability="cap.query_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                sql="SELECT run_id, topic, outputs_json FROM runs WHERE run_id = ? LIMIT 1",
                params=[run_id],
                db_path=str(Path(workspace) / "index" / "agent.db"),
            )
            if not read_res.ok:
                raise RuntimeError(read_res.error)
            rows = read_res.data.get("rows", [])
            if not rows:
                raise ValueError("run not found for run_id")
            run_row = rows[0]
            outputs = json.loads(run_row.get("outputs_json") or "{}")
            candidates = outputs.get("candidates", [])
            for c in candidates:
                url = c.get("url")
                if not url:
                    continue
                dup_res = use_tool(
                    orch,
                    capability="cap.query_rows",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"url": url},
                    sql="SELECT id FROM documents WHERE url = ? LIMIT 1",
                    params=[url],
                )
                if not dup_res.ok:
                    raise RuntimeError(dup_res.error)
                if dup_res.data.get("rows"):
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
                    raise RuntimeError(fetch_res.error)
                text = extract_readable_text(fetch_res.data.get("text") or "")
                title = str(c.get("title") or "")
                summary = str(c.get("snippet") or "")
                if regenerate_summary or not (title and summary):
                    prompt = text[:6000]
                    prompt = f"URL: {url}\n\nCONTENT:\n{prompt}"
                    llm_res = use_tool(
                        orch,
                        capability="cap.llm_generate",
                        run_id=ops_run_id,
                        skill_name=self.spec.name,
                        parameters={"url": url},
                        system=SYSTEM_SUMMARIZE,
                        user=prompt,
                        temperature=0.2,
                    )
                    if not llm_res.ok:
                        raise RuntimeError(llm_res.error)
                    llm_out = _parse_summary_json(str(llm_res.data.get("text") or ""))
                    title = llm_out.get("title") or title
                    summary = llm_out.get("summary") or summary
                doc_id = str(uuid.uuid4())
                now = datetime.now()
                folder = (
                    Path(workspace)
                    / "content"
                    / "documents"
                    / now.strftime("%Y")
                    / now.strftime("%m")
                    / doc_id
                )
                doc_path = folder / "doc.md"
                fm = {
                    "id": doc_id,
                    "type": "document",
                    "title": title,
                    "url": url,
                    "retrieved_at": utc_now_iso(),
                    "run_id": run_id,
                    "summary": summary,
                    "tags": [],
                    "taxonomies": {"domain": [], "use_case": [], "risk": [], "maturity": []},
                    "source": f"Web search query: {run_row.get('topic','')}\nResult title: {c.get('title','')}",
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
                    raise RuntimeError(write_res.error)
                created.append(str(doc_path))
            outputs["documents_created"] = created
            update_res = use_tool(
                orch,
                capability="cap.update_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                sql="UPDATE runs SET outputs_json = ?, ended_at = ? WHERE run_id = ?",
                params=[json.dumps(outputs), utc_now_iso(), run_id],
                db_path=str(Path(workspace) / "index" / "agent.db"),
            )
            if not update_res.ok:
                raise RuntimeError(update_res.error)
            return {"created_docs": created, "skipped": skipped}
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)


class IndexDocumentsFromRun(Skill):
    spec = SkillSpec(
        name="index_documents_from_run",
        required_capabilities=["cap.query_rows", "cap.indexing", "cap.ops_logging"],
    )

    def run(
        self,
        orch,
        *,
        run_id: str,
        workspace: Path,
        agent_name: str,
        agent_type: str,
        parent_run_id: str | None = None,
    ) -> int:
        ops_run_id = start_ops_run(
            orch,
            agent_name=agent_name,
            agent_type=agent_type,
            purpose=f"index-docs:{run_id}",
            parent_run_id=parent_run_id,
        )
        status = "completed"
        try:
            read_res = use_tool(
                orch,
                capability="cap.query_rows",
                run_id=ops_run_id,
                skill_name=self.spec.name,
                sql="SELECT outputs_json FROM runs WHERE run_id = ? LIMIT 1",
                params=[run_id],
                db_path=str(Path(workspace) / "index" / "agent.db"),
            )
            if not read_res.ok:
                raise RuntimeError(read_res.error)
            rows = read_res.data.get("rows", [])
            if not rows:
                raise ValueError("run not found for run_id")
            outputs = json.loads(rows[0].get("outputs_json") or "{}")
            doc_paths = outputs.get("documents_created", [])
            for p in doc_paths:
                index_res = use_tool(
                    orch,
                    capability="cap.indexing",
                    run_id=ops_run_id,
                    skill_name=self.spec.name,
                    parameters={"path": str(p)},
                    doc_path=str(p),
                )
                if not index_res.ok:
                    raise RuntimeError(index_res.error)
            return len(doc_paths)
        except Exception:
            status = "error"
            raise
        finally:
            end_ops_run(orch, run_id=ops_run_id, status=status)
