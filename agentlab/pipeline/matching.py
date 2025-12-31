from __future__ import annotations
import json, uuid
from dataclasses import dataclass
from pathlib import Path
from agentlab.db.db import connect
from agentlab.providers.llm import get_provider

@dataclass
class MatchResult:
    match_id: str
    idea_id: str
    document_id: str
    match_score: float
    reasons: list[str]
    scores: dict[str, float | None]

SYSTEM_MATCH = """You are a careful research matcher for an applied research team.
Score matchness (0-10) between an IDEA/PROBLEM and a DOCUMENT.
Return strict JSON:
{
  "matchness": <0-10>,
  "reasons": ["...","..."],
  "novelty": <0-10 or null>,
  "credibility": <0-10 or null>,
  "actionability": <0-10 or null>,
  "taxonomy_fit": <0-10 or null>
}
Keep reasons short and evidence-based."""

def _heuristic_match(a: str, b: str) -> tuple[float, list[str]]:
    aw = {w.lower() for w in a.split() if len(w) > 4}
    bw = {w.lower() for w in b.split() if len(w) > 4}
    ov = sorted(list(aw & bw))
    score = min(10.0, (len(ov) / max(8, len(aw))) * 10.0)
    reason = f"Overlapping terms: {', '.join(ov[:12])}" if ov else "Low lexical overlap (heuristic baseline)."
    return score, [reason]

def score_match(idea_md: str, doc_md: str) -> tuple[float, list[str], dict[str, float | None]]:
    llm = get_provider()
    if llm.__class__.__name__ != "HeuristicLLM":
        try:
            out = llm.complete(SYSTEM_MATCH, f"IDEA:\n{idea_md[:6000]}\n\nDOCUMENT:\n{doc_md[:6000]}\n").text
            data = json.loads(out)
            matchness = float(data.get("matchness", 0.0))
            reasons = data.get("reasons") if isinstance(data.get("reasons"), list) else []
            scores = {k: data.get(k) for k in ["novelty","credibility","actionability","taxonomy_fit"]}
            for k,v in list(scores.items()):
                if v is None: continue
                try: scores[k] = float(v)
                except Exception: scores[k] = None
            return matchness, [str(r) for r in reasons][:6], scores
        except Exception:
            pass
    h, reasons = _heuristic_match(idea_md, doc_md)
    return h, reasons, {"novelty": None, "credibility": None, "actionability": None, "taxonomy_fit": None}

def match_idea_to_docs(db_path: Path, idea_id: str, top_n: int = 10) -> list[MatchResult]:
    con = connect(db_path)
    idea = con.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
    if not idea: raise ValueError(f"idea not found: {idea_id}")
    idea_text = Path(idea["content_path"]).read_text(encoding="utf-8")
    existing = {
        r["document_id"]: r["id"]
        for r in con.execute("SELECT id, document_id FROM matches WHERE idea_id=?", (idea_id,)).fetchall()
    }
    docs = con.execute("SELECT * FROM documents ORDER BY retrieved_at DESC").fetchall()
    results=[]
    for d in docs[:200]:
        doc_path = Path(d["content_path"])
        if not doc_path.exists():
            continue
        doc_text = doc_path.read_text(encoding="utf-8")
        m, reasons, scores = score_match(idea_text, doc_text)
        match_id = existing.get(d["id"]) or str(uuid.uuid4())
        results.append(MatchResult(match_id, idea_id, d["id"], m, reasons, scores))
    results.sort(key=lambda r: r.match_score, reverse=True)
    results = results[:top_n]
    for r in results:
        con.execute(
            """INSERT INTO matches(id,idea_id,document_id,match_score,reasons_json,scores_json)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(idea_id, document_id) DO UPDATE SET
                 match_score=excluded.match_score,
                 reasons_json=excluded.reasons_json,
                 scores_json=excluded.scores_json
            """,
            (r.match_id, r.idea_id, r.document_id, float(r.match_score), json.dumps(r.reasons), json.dumps(r.scores)),
        )
    con.commit(); con.close()
    return results

def match_doc_to_ideas(db_path: Path, document_id: str, top_n: int = 10) -> list[MatchResult]:
    con = connect(db_path)
    doc = con.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
    if not doc: raise ValueError(f"doc not found: {document_id}")
    doc_path = Path(doc["content_path"])
    if not doc_path.exists():
        con.close()
        return []
    doc_text = doc_path.read_text(encoding="utf-8")
    existing = {
        r["idea_id"]: r["id"]
        for r in con.execute("SELECT id, idea_id FROM matches WHERE document_id=?", (document_id,)).fetchall()
    }
    ideas = con.execute("SELECT * FROM ideas ORDER BY created_at DESC").fetchall()
    results=[]
    for i in ideas[:200]:
        idea_path = Path(i["content_path"])
        if not idea_path.exists():
            continue
        idea_text = idea_path.read_text(encoding="utf-8")
        m, reasons, scores = score_match(idea_text, doc_text)
        match_id = existing.get(i["id"]) or str(uuid.uuid4())
        results.append(MatchResult(match_id, i["id"], document_id, m, reasons, scores))
    results.sort(key=lambda r: r.match_score, reverse=True)
    results = results[:top_n]
    for r in results:
        con.execute(
            """INSERT INTO matches(id,idea_id,document_id,match_score,reasons_json,scores_json)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(idea_id, document_id) DO UPDATE SET
                 match_score=excluded.match_score,
                 reasons_json=excluded.reasons_json,
                 scores_json=excluded.scores_json
            """,
            (r.match_id, r.idea_id, r.document_id, float(r.match_score), json.dumps(r.reasons), json.dumps(r.scores)),
        )
    con.commit(); con.close()
    return results
