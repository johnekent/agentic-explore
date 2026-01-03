from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from agentlab.core.paths import ensure_workspace, utc_now_iso
from agentlab.db.db import connect, apply_migrations_from_dir, with_retry


def log_usage(
    skill_name: str,
    agent_type: str,
    workflow_context: str = None,
    parameters: dict | None = None,
    result_summary: str = None,
    duration_ms: int | None = None,
    db_path: str | None = None,
):
    """Log skill usage for operational dashboard."""
    if db_path is None:
        ws = ensure_workspace(Path("workspace"))
        db_path = str(ws.db_path)
    con = connect(Path(db_path))
    apply_migrations_from_dir(con, Path("db/migrations"))
    log_id = str(uuid.uuid4())
    timestamp = utc_now_iso()
    params_json = json.dumps(parameters) if parameters else None
    with_retry(
        lambda: con.execute(
        """
        INSERT INTO usage_logs (id, timestamp, skill_name, agent_type, workflow_context, parameters_json, result_summary, duration_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (log_id, timestamp, skill_name, agent_type, workflow_context, params_json, result_summary, duration_ms),
        )
    )
    con.commit()
    con.close()


def start_run(
    agent_name: str,
    agent_type: str,
    *,
    purpose: str | None = None,
    parent_run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> str:
    if db_path is None:
        ws = ensure_workspace(Path("workspace"))
        db_path = ws.db_path
    con = connect(db_path)
    apply_migrations_from_dir(con, Path("db/migrations"))
    run_id = str(uuid.uuid4())
    with_retry(
        lambda: con.execute(
        """
        INSERT INTO agent_runs (id, agent_name, agent_type, purpose, status, started_at, parent_run_id, metadata_json)
        VALUES (?, ?, ?, ?, 'started', ?, ?, ?)
        """,
        (run_id, agent_name, agent_type, purpose, utc_now_iso(), parent_run_id, json.dumps(metadata) if metadata else None),
        )
    )
    if parent_run_id:
        with_retry(
            lambda: con.execute(
            """
            INSERT INTO agent_interactions (id, run_id, with_agent, interaction_type, details_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                parent_run_id,
                agent_name,
                "agent_invocation",
                json.dumps({"child_run_id": run_id, "purpose": purpose}),
                utc_now_iso(),
            ),
            )
        )
    con.commit()
    con.close()
    return run_id


def end_run(run_id: str, *, status: str = "completed", db_path: Path | None = None) -> None:
    if db_path is None:
        ws = ensure_workspace(Path("workspace"))
        db_path = ws.db_path
    con = connect(db_path)
    apply_migrations_from_dir(con, Path("db/migrations"))
    with_retry(
        lambda: con.execute(
            "UPDATE agent_runs SET status = ?, ended_at = ? WHERE id = ?",
            (status, utc_now_iso(), run_id),
        )
    )
    con.commit()
    con.close()


def log_tool_call(
    run_id: str,
    tool_name: str,
    *,
    skill_name: str | None = None,
    parameters: dict[str, Any] | None = None,
    result_summary: str | None = None,
    duration_ms: int | None = None,
    db_path: Path | None = None,
) -> None:
    if db_path is None:
        ws = ensure_workspace(Path("workspace"))
        db_path = ws.db_path
    con = connect(db_path)
    apply_migrations_from_dir(con, Path("db/migrations"))
    call_id = str(uuid.uuid4())
    with_retry(
        lambda: con.execute(
        """
        INSERT INTO tool_calls (id, run_id, tool_name, skill_name, parameters_json, result_summary, duration_ms, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            call_id,
            run_id,
            tool_name,
            skill_name,
            json.dumps(parameters) if parameters else None,
            result_summary,
            duration_ms,
            utc_now_iso(),
        ),
        )
    )
    with_retry(
        lambda: con.execute(
        """
        INSERT INTO agent_interactions (id, run_id, with_agent, interaction_type, details_json, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            run_id,
            tool_name,
            "tool_call",
            json.dumps({"tool_call_id": call_id, "skill_name": skill_name}),
            utc_now_iso(),
        ),
        )
    )
    if skill_name:
        with_retry(
            lambda: con.execute(
            """
            INSERT INTO agent_interactions (id, run_id, with_agent, interaction_type, details_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                run_id,
                skill_name,
                "skill_use",
                json.dumps({"tool_call_id": call_id, "tool_name": tool_name}),
                utc_now_iso(),
            ),
            )
        )
    con.commit()
    con.close()


def log_interaction(
    run_id: str,
    with_agent: str,
    interaction_type: str,
    *,
    details: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> None:
    if db_path is None:
        ws = ensure_workspace(Path("workspace"))
        db_path = ws.db_path
    con = connect(db_path)
    apply_migrations_from_dir(con, Path("db/migrations"))
    interaction_id = str(uuid.uuid4())
    with_retry(
        lambda: con.execute(
        """
        INSERT INTO agent_interactions (id, run_id, with_agent, interaction_type, details_json, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (interaction_id, run_id, with_agent, interaction_type, json.dumps(details) if details else None, utc_now_iso()),
        )
    )
    con.commit()
    con.close()


def log_span(
    run_id: str,
    span_name: str,
    *,
    skill_name: str | None = None,
    category: str | None = None,
    status: str = "ok",
    duration_ms: int,
    started_at: str,
    ended_at: str,
    metadata: dict[str, Any] | None = None,
    parent_span_id: str | None = None,
    db_path: Path | None = None,
) -> None:
    if db_path is None:
        ws = ensure_workspace(Path("workspace"))
        db_path = ws.db_path
    con = connect(db_path)
    apply_migrations_from_dir(con, Path("db/migrations"))
    span_id = str(uuid.uuid4())
    with_retry(
        lambda: con.execute(
        """
        INSERT INTO perf_spans (id, run_id, span_name, span_category, skill_name, status, started_at, ended_at, duration_ms, metadata_json, parent_span_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            span_id,
            run_id,
            span_name,
            category,
            skill_name,
            status,
            started_at,
            ended_at,
            duration_ms,
            json.dumps(metadata) if metadata else None,
            parent_span_id,
        ),
        )
    )
    con.commit()
    con.close()
