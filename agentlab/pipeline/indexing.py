from __future__ import annotations
from pathlib import Path
from agentlab.core.frontmatter import parse_md_with_frontmatter
from agentlab.db.db import connect

def upsert_document(db_path: Path, doc_path: Path) -> str:
    con = connect(db_path)
    md = parse_md_with_frontmatter(doc_path.read_text(encoding="utf-8"))
    fm = md.frontmatter
    doc_id = str(fm.get("id"))
    tax = fm.get("taxonomies") if isinstance(fm.get("taxonomies"), dict) else {}
    review = fm.get("review") if isinstance(fm.get("review"), dict) else {}
    con.execute(
        """INSERT INTO documents(
             id,title,url,retrieved_at,summary,content_path,source_text,run_id,review_score,review_notes,
             asset_type,asset_ref,asset_path
           )
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             title=excluded.title,url=excluded.url,retrieved_at=excluded.retrieved_at,summary=excluded.summary,
             content_path=excluded.content_path,source_text=excluded.source_text,run_id=excluded.run_id,
             asset_type=excluded.asset_type,asset_ref=excluded.asset_ref,asset_path=excluded.asset_path,
             review_score=coalesce(excluded.review_score, documents.review_score),
             review_notes=coalesce(excluded.review_notes, documents.review_notes)
        """,
        (doc_id, fm.get("title"), fm.get("url"), fm.get("retrieved_at"), fm.get("summary"),
         str(doc_path), fm.get("source") or "", fm.get("run_id"), review.get("score"), review.get("notes"),
         fm.get("asset_type"), fm.get("asset_ref"), fm.get("asset_path"))
    )
    con.execute("DELETE FROM document_taxonomy WHERE document_id=?", (doc_id,))
    for tax_name, labels in (tax or {}).items():
        if isinstance(labels, list):
            for lab in labels:
                con.execute("INSERT OR IGNORE INTO document_taxonomy(document_id,taxonomy_name,label) VALUES (?,?,?)",
                            (doc_id, str(tax_name), str(lab)))
    con.commit(); con.close()
    return doc_id

def upsert_idea(db_path: Path, idea_path: Path) -> str:
    con = connect(db_path)
    md = parse_md_with_frontmatter(idea_path.read_text(encoding="utf-8"))
    fm = md.frontmatter
    idea_id = str(fm.get("id"))
    tax = fm.get("taxonomies") if isinstance(fm.get("taxonomies"), dict) else {}
    review = fm.get("review") if isinstance(fm.get("review"), dict) else {}
    summary = fm.get("summary") or (md.body.strip().splitlines()[:1] or [""])[0][:300]
    con.execute(
        """INSERT INTO ideas(id,title,summary,proposed_by,created_at,status,content_path,source_text,review_score,review_notes)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
             title=excluded.title,summary=excluded.summary,proposed_by=excluded.proposed_by,created_at=excluded.created_at,
             status=excluded.status,content_path=excluded.content_path,source_text=excluded.source_text,
             review_score=coalesce(excluded.review_score, ideas.review_score),
             review_notes=coalesce(excluded.review_notes, ideas.review_notes)
        """,
        (idea_id, fm.get("title"), summary, fm.get("proposed_by"), fm.get("created_at"), fm.get("status"),
         str(idea_path), fm.get("source") or "", review.get("score"), review.get("notes"))
    )
    con.execute("DELETE FROM idea_taxonomy WHERE idea_id=?", (idea_id,))
    for tax_name, labels in (tax or {}).items():
        if isinstance(labels, list):
            for lab in labels:
                con.execute("INSERT OR IGNORE INTO idea_taxonomy(idea_id,taxonomy_name,label) VALUES (?,?,?)",
                            (idea_id, str(tax_name), str(lab)))
    con.commit(); con.close()
    return idea_id
