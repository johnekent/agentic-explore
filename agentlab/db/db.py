from __future__ import annotations
import sqlite3
import time
from pathlib import Path

def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("PRAGMA foreign_keys = ON;")
    con.execute("PRAGMA busy_timeout = 5000;")
    return con

def with_retry(fn, *, retries: int = 3, delay_s: float = 0.2):
    for attempt in range(retries):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == retries - 1:
                raise
            time.sleep(delay_s)

def apply_migration(con: sqlite3.Connection, sql_text: str) -> None:
    con.executescript(sql_text)
    con.commit()

def _ensure_migrations_table(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          name TEXT PRIMARY KEY,
          applied_at TEXT NOT NULL
        )
        """
    )
    con.commit()

def _migration_applied(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute("SELECT 1 FROM schema_migrations WHERE name = ?", (name,)).fetchone()
    return row is not None

def _record_migration(con: sqlite3.Connection, name: str) -> None:
    con.execute("INSERT OR IGNORE INTO schema_migrations(name, applied_at) VALUES (?, datetime('now'))", (name,))
    con.commit()

def _is_duplicate_schema_error(exc: sqlite3.OperationalError) -> bool:
    msg = str(exc).lower()
    return "duplicate column name" in msg or "already exists" in msg

def _migration_appears_applied(con: sqlite3.Connection, name: str) -> bool:
    if name == "003_item_processing.sql":
        cols = {row["name"] for row in con.execute("PRAGMA table_info(documents)").fetchall()}
        if not {"asset_type", "asset_ref", "asset_path"}.issubset(cols):
            return False
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'item_processing'"
        ).fetchone()
        return row is not None
    return True

def apply_migrations_from_dir(con: sqlite3.Connection, migrations_dir: Path) -> None:
    if not migrations_dir.exists():
        return
    _ensure_migrations_table(con)
    for path in sorted(migrations_dir.glob("*.sql")):
        if _migration_applied(con, path.name):
            continue
        try:
            apply_migration(con, path.read_text(encoding="utf-8"))
        except sqlite3.OperationalError as exc:
            if _is_duplicate_schema_error(exc) and _migration_appears_applied(con, path.name):
                _record_migration(con, path.name)
                continue
            raise
        _record_migration(con, path.name)
