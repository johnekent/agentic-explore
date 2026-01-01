from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any

from agentlab.core.paths import ensure_workspace
from agentlab.db.db import connect
from agentlab.pipeline.embeddings import load_vec_extension


def cleanup_db_records(ws_root: Path, *, dry_run: bool = True) -> dict[str, Any]:
    """
    Remove records that reference missing content files or missing parents.
    """
    ws = ensure_workspace(ws_root)
    con = connect(ws.db_path)

    doc_rows = con.execute("SELECT id, content_path FROM documents").fetchall()
    idea_rows = con.execute("SELECT id, content_path FROM ideas").fetchall()
    doc_ids = {r["id"] for r in doc_rows}
    idea_ids = {r["id"] for r in idea_rows}

    missing_doc_ids = [r["id"] for r in doc_rows if not Path(r["content_path"]).exists()]
    missing_idea_ids = [r["id"] for r in idea_rows if not Path(r["content_path"]).exists()]

    match_rows = con.execute("SELECT id, idea_id, document_id FROM matches").fetchall()
    missing_match_ids = [
        r["id"]
        for r in match_rows
        if r["idea_id"] not in idea_ids or r["document_id"] not in doc_ids
    ]

    task_rows = con.execute("SELECT id, match_id FROM tasks WHERE match_id IS NOT NULL").fetchall()
    match_ids = {r["id"] for r in match_rows}
    missing_task_ids = [r["id"] for r in task_rows if r["match_id"] not in match_ids]

    report = {
        "dry_run": dry_run,
        "missing_documents": len(missing_doc_ids),
        "missing_ideas": len(missing_idea_ids),
        "orphan_matches": len(missing_match_ids),
        "orphan_tasks": len(missing_task_ids),
    }

    if not dry_run:
        if missing_task_ids:
            con.execute(
                "DELETE FROM tasks WHERE id IN (%s)" % ",".join("?" * len(missing_task_ids)),
                missing_task_ids,
            )
        if missing_match_ids:
            con.execute(
                "DELETE FROM matches WHERE id IN (%s)" % ",".join("?" * len(missing_match_ids)),
                missing_match_ids,
            )
        if missing_doc_ids:
            con.execute(
                "DELETE FROM documents WHERE id IN (%s)" % ",".join("?" * len(missing_doc_ids)),
                missing_doc_ids,
            )
        if missing_idea_ids:
            con.execute(
                "DELETE FROM ideas WHERE id IN (%s)" % ",".join("?" * len(missing_idea_ids)),
                missing_idea_ids,
            )
        con.commit()

    con.close()
    return report


def delete_all_data_records(ws_root: Path, *, delete_files: bool = True) -> dict[str, Any]:
    """
    Delete all rows from every user table in the SQLite database.
    """
    ws = ensure_workspace(ws_root)
    con = connect(ws.db_path)
    doc_paths = [r["content_path"] for r in con.execute("SELECT content_path FROM documents").fetchall()]
    idea_paths = [r["content_path"] for r in con.execute("SELECT content_path FROM ideas").fetchall()]
    con.execute("PRAGMA foreign_keys = OFF")
    table_rows = con.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    tables = [r["name"] for r in table_rows]
    if any(r["sql"] and "vec0" in r["sql"].lower() for r in table_rows):
        load_vec_extension(con)
    report: dict[str, Any] = {"tables": {}}
    for table in tables:
        safe_name = table.replace('"', '""')
        cur = con.execute(f'DELETE FROM "{safe_name}"')
        report["tables"][table] = int(cur.rowcount if cur.rowcount != -1 else 0)
    con.commit()
    con.execute("PRAGMA foreign_keys = ON")
    con.close()
    if delete_files:
        deleted = 0
        missing = 0
        for path_str in doc_paths + idea_paths:
            try:
                path = Path(path_str)
                if path.exists():
                    path.unlink()
                    deleted += 1
                else:
                    missing += 1
            except Exception:
                missing += 1
        report["files_deleted"] = deleted
        report["files_missing"] = missing
        runs_dir = ws_root / "runs"
        if runs_dir.exists():
            try:
                shutil.rmtree(runs_dir)
                report["runs_deleted"] = True
            except Exception:
                report["runs_deleted"] = False
    report["total_tables"] = len(tables)
    report["total_rows"] = sum(report["tables"].values())
    return report
