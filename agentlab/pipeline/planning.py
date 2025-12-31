from __future__ import annotations
from pathlib import Path
from agentlab.core.paths import ensure_workspace, utc_now_iso
from agentlab.db.db import connect
import uuid

def plan_match_execution(ws_root: Path, match_id: str):
    """
    Create a task for executing a reviewed match.
    """
    ws = ensure_workspace(ws_root)
    con = connect(ws.db_path)

    task_id = str(uuid.uuid4())
    description = f"Execute match {match_id}"
    created_at = utc_now_iso()

    con.execute("""
        INSERT INTO tasks (id, description, status, priority, match_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (task_id, description, 'pending', 'medium', match_id, created_at))
    con.commit()
    con.close()

    return task_id

def get_task_backlog(ws_root: Path):
    """
    Get pending and in_progress tasks for planning.
    """
    ws = ensure_workspace(ws_root)
    con = connect(ws.db_path)
    tasks = con.execute("SELECT * FROM tasks WHERE status IN ('pending', 'in_progress')").fetchall()
    con.close()
    return tasks

def update_task_status(ws_root: Path, task_id: str, status: str):
    """
    Update task status.
    """
    ws = ensure_workspace(ws_root)
    con = connect(ws.db_path)
    updated_at = utc_now_iso()
    con.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?", (status, updated_at, task_id))
    con.commit()
    con.close()

def assign_task_agent(ws_root: Path, task_id: str, agent: str):
    """
    Assign an agent to a task.
    """
    ws = ensure_workspace(ws_root)
    con = connect(ws.db_path)
    updated_at = utc_now_iso()
    con.execute("UPDATE tasks SET assigned_agent = ?, updated_at = ? WHERE id = ?", (agent, updated_at, task_id))
    con.commit()
    con.close()