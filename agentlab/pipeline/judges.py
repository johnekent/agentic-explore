from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from agentlab.db.db import connect
from agentlab.core.frontmatter import parse_md_with_frontmatter

def judge_validity(db_path: Path) -> dict[str, list[dict[str, Any]]]:
    con = connect(db_path)
    failures = {"documents": [], "ideas": [], "matches": []}

    for row in con.execute("SELECT * FROM documents").fetchall():
        p = Path(row["content_path"])
        if not p.exists():
            failures["documents"].append({"id": row["id"], "error": "missing file", "path": row["content_path"]})
            continue
        md = parse_md_with_frontmatter(p.read_text(encoding="utf-8"))
        fm = md.frontmatter
        missing = {
            "source": not (isinstance(fm.get("source"), str) and fm.get("source").strip()),
            "retrieved_at": not bool(fm.get("retrieved_at")),
            "url": not bool(fm.get("url")),
        }
        if any(missing.values()):
            failures["documents"].append({"id": row["id"], "missing": missing, "path": str(p)})

    for row in con.execute("SELECT * FROM ideas").fetchall():
        p = Path(row["content_path"])
        if not p.exists():
            failures["ideas"].append({"id": row["id"], "error": "missing file", "path": row["content_path"]})
            continue
        md = parse_md_with_frontmatter(p.read_text(encoding="utf-8"))
        fm = md.frontmatter
        missing = {
            "source": not (isinstance(fm.get("source"), str) and fm.get("source").strip()),
            "proposed_by": not bool(fm.get("proposed_by")),
        }
        if any(missing.values()):
            failures["ideas"].append({"id": row["id"], "missing": missing, "path": str(p)})

    con.close()
    return failures

def build_dashboard_md(db_path: Path, out_path: Path) -> None:
    con = connect(db_path)
    docs = con.execute("SELECT id,title,url,retrieved_at,review_score FROM documents ORDER BY retrieved_at DESC LIMIT 20").fetchall()
    ideas = con.execute("SELECT id,title,proposed_by,created_at,review_score FROM ideas ORDER BY created_at DESC LIMIT 20").fetchall()
    matches = con.execute("SELECT id,idea_id,document_id,match_score FROM matches ORDER BY match_score DESC LIMIT 20").fetchall()
    con.close()

    lines = ["# Agent Dashboard\n"]
    lines.append("## Recent documents\n")
    for d in docs:
        lines.append(f"- **{d['title'] or d['id']}** (doc_score={d['review_score']})\n  - {d['url']}\n")
    lines.append("\n## Recent ideas\n")
    for i in ideas:
        lines.append(f"- **{i['title'] or i['id']}** (by {i['proposed_by']}, idea_score={i['review_score']})\n")
    lines.append("\n## Top matches\n")
    for m in matches:
        lines.append(f"- match={m['id']} idea={m['idea_id']} doc={m['document_id']} **matchness={m['match_score']:.1f}/10**\n")
    lines.append("\n## Human scoring hook\n")
    lines.append("Add to any doc/idea frontmatter:\n```yaml\nreview:\n  score: 0-10\n  notes: \"...\"\n```\n")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
