from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentlab.core.config import get_setting
from agentlab.db.db import apply_migrations_from_dir, connect
from agentlab.core.paths import ensure_workspace
from agentlab.tools.types import ToolResult


def _db_path() -> Path:
    return Path(get_setting("AGENTLAB_DB_PATH", "workspace/index/agent.db"))


def _resolve_db_path(db_path: str | None = None) -> Path:
    return Path(db_path) if db_path else _db_path()


def query_rows(sql: str, params: list[Any] | None = None, db_path: str | None = None) -> ToolResult:
    if not sql.strip().lower().startswith("select"):
        return ToolResult.failure("invalid_sql", "Only SELECT is allowed.")
    try:
        con = connect(_resolve_db_path(db_path))
        rows = [dict(r) for r in con.execute(sql, params or []).fetchall()]
        con.close()
        return ToolResult.success({"rows": rows})
    except sqlite3.Error as exc:
        return ToolResult.failure("sqlite_error", str(exc))


def persist_rows(table: str, rows: list[dict[str, Any]], mode: str = "insert", db_path: str | None = None) -> ToolResult:
    if not rows:
        return ToolResult.success({"inserted": 0})
    try:
        con = connect(_resolve_db_path(db_path))
        cols = list(rows[0].keys())
        placeholders = ",".join("?" * len(cols))
        insert_sql = "INSERT"
        if mode == "ignore":
            insert_sql = "INSERT OR IGNORE"
        elif mode == "replace":
            insert_sql = "INSERT OR REPLACE"
        sql = f"{insert_sql} INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        values = [tuple(r.get(c) for c in cols) for r in rows]
        con.executemany(sql, values)
        con.commit()
        con.close()
        return ToolResult.success({"inserted": len(rows)})
    except sqlite3.Error as exc:
        return ToolResult.failure("sqlite_error", str(exc))


def update_rows(sql: str, params: list[Any] | None = None, db_path: str | None = None) -> ToolResult:
    if not sql.strip().lower().startswith("update"):
        return ToolResult.failure("invalid_sql", "Only UPDATE is allowed.")
    try:
        con = connect(_resolve_db_path(db_path))
        cur = con.execute(sql, params or [])
        con.commit()
        con.close()
        return ToolResult.success({"updated": cur.rowcount})
    except sqlite3.Error as exc:
        return ToolResult.failure("sqlite_error", str(exc))


def delete_rows(sql: str, params: list[Any] | None = None, db_path: str | None = None) -> ToolResult:
    lower = sql.strip().lower()
    if not lower.startswith("delete"):
        return ToolResult.failure("invalid_sql", "Only DELETE is allowed.")
    if " where " not in lower:
        return ToolResult.failure("unsafe_sql", "DELETE must include a WHERE clause.")
    try:
        con = connect(_resolve_db_path(db_path))
        cur = con.execute(sql, params or [])
        con.commit()
        con.close()
        return ToolResult.success({"deleted": cur.rowcount})
    except sqlite3.Error as exc:
        return ToolResult.failure("sqlite_error", str(exc))


def migrate_db(workspace: str, migrations_dir: str) -> ToolResult:
    try:
        ws = ensure_workspace(Path(workspace))
        con = connect(ws.db_path)
        migrations_path = Path(migrations_dir)
        if not migrations_path.exists():
            repo_root = Path(__file__).resolve().parents[2]
            fallback = repo_root / "db" / "migrations"
            if fallback.exists():
                migrations_path = fallback
        if not migrations_path.exists():
            return ToolResult.failure(
                "migrations_missing",
                f"migrations_dir not found: {migrations_dir}",
            )
        apply_migrations_from_dir(con, migrations_path)
        con.close()
        return ToolResult.success({"db_path": str(ws.db_path), "migrations_dir": str(migrations_path)})
    except sqlite3.Error as exc:
        return ToolResult.failure("sqlite_error", str(exc))
    except Exception as exc:
        return ToolResult.failure("migrate_error", str(exc))
