from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def check_lock(db_path: Path, timeout_ms: int) -> int:
    con = sqlite3.connect(str(db_path))
    con.execute(f"PRAGMA busy_timeout = {timeout_ms};")
    try:
        con.execute("BEGIN IMMEDIATE;")
        con.execute("ROLLBACK;")
        return 0
    except Exception as exc:
        print(f"LOCKED: {exc}")
        return 1
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check if the SQLite DB can acquire a write lock.")
    parser.add_argument("--db", default="workspace/index/agent.db", help="Path to SQLite DB")
    parser.add_argument("--timeout_ms", type=int, default=1000, help="Busy timeout in ms")
    args = parser.parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB not found: {db_path}")
        return 2
    code = check_lock(db_path, args.timeout_ms)
    if code == 0:
        print("OK: acquired write lock")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
