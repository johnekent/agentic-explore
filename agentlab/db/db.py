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

def apply_migrations_from_dir(con: sqlite3.Connection, migrations_dir: Path) -> None:
    if not migrations_dir.exists():
        return
    for path in sorted(migrations_dir.glob("*.sql")):
        apply_migration(con, path.read_text(encoding="utf-8"))
