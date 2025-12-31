from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentlab.core.paths import ensure_workspace
from agentlab.db.db import connect


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
