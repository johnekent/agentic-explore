from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from agentlab.db.db import connect


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_url_duplicate(db_path: Path, url: str) -> bool:
    if not url:
        return False
    con = connect(db_path)
    row = con.execute("SELECT id FROM documents WHERE url=? LIMIT 1", (url,)).fetchone()
    con.close()
    return row is not None


def find_duplicate_groups(db_path: Path) -> list[dict[str, Any]]:
    con = connect(db_path)
    groups: list[dict[str, Any]] = []

    # URL-based duplicates
    url_rows = con.execute(
        "SELECT url, COUNT(*) AS c FROM documents WHERE url IS NOT NULL AND url != '' GROUP BY url HAVING c > 1"
    ).fetchall()
    for r in url_rows:
        url = r["url"]
        docs = con.execute(
            "SELECT id, title, summary, url, content_path FROM documents WHERE url=?",
            (url,),
        ).fetchall()
        groups.append(
            {
                "key": f"url:{url}",
                "reason": "url",
                "doc_ids": [d["id"] for d in docs],
                "docs": [dict(d) for d in docs],
            }
        )

    # Title+summary text duplicates
    rows = con.execute(
        "SELECT id, title, summary, url, content_path FROM documents"
    ).fetchall()
    buckets: dict[str, list[dict[str, Any]]] = {}
    for d in rows:
        norm = _normalize(f"{d['title'] or ''} {d['summary'] or ''}")
        if not norm:
            continue
        key = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        buckets.setdefault(key, []).append(dict(d))
    for key, docs in buckets.items():
        if len(docs) < 2:
            continue
        groups.append(
            {
                "key": f"text:{key}",
                "reason": "title+summary",
                "doc_ids": [d["id"] for d in docs],
                "docs": docs,
            }
        )

    con.close()
    return groups


def delete_documents(db_path: Path, doc_ids: list[str], delete_files: bool = True) -> dict[str, Any]:
    if not doc_ids:
        return {"deleted": 0, "files_deleted": 0}
    con = connect(db_path)
    placeholders = ",".join("?" * len(doc_ids))
    rows = con.execute(
        f"SELECT id, content_path FROM documents WHERE id IN ({placeholders})",
        doc_ids,
    ).fetchall()
    con.execute(f"DELETE FROM documents WHERE id IN ({placeholders})", doc_ids)
    con.commit()
    con.close()

    files_deleted = 0
    if delete_files:
        for r in rows:
            p = Path(r["content_path"])
            if p.exists():
                try:
                    p.unlink()
                    files_deleted += 1
                except Exception:
                    continue
    return {"deleted": len(rows), "files_deleted": files_deleted}
