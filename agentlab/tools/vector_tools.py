from __future__ import annotations

from pathlib import Path

from agentlab.pipeline.embeddings import (
    DEFAULT_EMBED_MODEL,
    batch_encode,
    ensure_vec_tables,
    load_vec_extension,
    serialize_vector,
    upsert_embeddings,
)
from agentlab.db.db import connect
from agentlab.tools.types import ToolResult


def vector_index(
    db_path: str,
    *,
    model_name: str = DEFAULT_EMBED_MODEL,
    batch_size: int = 64,
    include_docs: bool = True,
    include_ideas: bool = True,
) -> ToolResult:
    try:
        con = connect(Path(db_path))
        load_vec_extension(con)
        def rebuild():
            con.execute("DROP TABLE IF EXISTS doc_embeddings")
            con.execute("DROP TABLE IF EXISTS idea_embeddings")
            ensure_vec_tables(con)

        def build() -> tuple[int, int]:
            ensure_vec_tables(con)
            doc_count = 0
            idea_count = 0

            if include_docs:
                docs = con.execute("SELECT id, title, summary, source_text FROM documents").fetchall()
                for start in range(0, len(docs), batch_size):
                    chunk = docs[start:start + batch_size]
                    ids = [r["id"] for r in chunk]
                    texts = [
                        "\n".join([str(r["title"] or ""), str(r["summary"] or ""), str(r["source_text"] or "")])
                        for r in chunk
                    ]
                    vectors = batch_encode(texts, model_name=model_name)
                    upsert_embeddings(con, table="doc_embeddings", id_field="doc_id", ids=ids, vectors=vectors)
                    doc_count += len(ids)

            if include_ideas:
                ideas = con.execute("SELECT id, title, summary, source_text FROM ideas").fetchall()
                for start in range(0, len(ideas), batch_size):
                    chunk = ideas[start:start + batch_size]
                    ids = [r["id"] for r in chunk]
                    texts = [
                        "\n".join([str(r["title"] or ""), str(r["summary"] or ""), str(r["source_text"] or "")])
                        for r in chunk
                    ]
                    vectors = batch_encode(texts, model_name=model_name)
                    upsert_embeddings(con, table="idea_embeddings", id_field="idea_id", ids=ids, vectors=vectors)
                    idea_count += len(ids)

            return doc_count, idea_count

        try:
            doc_count, idea_count = build()
        except Exception as exc:
            if "vector blob" in str(exc).lower():
                rebuild()
                doc_count, idea_count = build()
            else:
                raise

        con.commit()
        con.close()
        return ToolResult.success({"documents": doc_count, "ideas": idea_count})
    except Exception as exc:
        return ToolResult.failure("vector_index_error", str(exc))


def vector_query(
    db_path: str,
    query: str,
    *,
    limit: int = 20,
    model_name: str = DEFAULT_EMBED_MODEL,
) -> ToolResult:
    try:
        con = connect(Path(db_path))
        load_vec_extension(con)
        ensure_vec_tables(con)
        query_vec = batch_encode([query], model_name=model_name)[0]
        serialized = serialize_vector(query_vec)

        def query_table(table: str, id_field: str) -> list[dict[str, object]]:
            sql = f"SELECT {id_field}, distance FROM {table} WHERE embedding MATCH ? ORDER BY distance LIMIT ?"
            try:
                rows = con.execute(sql, (serialized, limit)).fetchall()
            except Exception:
                sql = f"SELECT {id_field} FROM {table} WHERE embedding MATCH ? LIMIT ?"
                rows = con.execute(sql, (serialized, limit)).fetchall()
                rows = [dict(r) | {"distance": None} for r in rows]
            return [dict(r) for r in rows]

        doc_hits = query_table("doc_embeddings", "doc_id")
        idea_hits = query_table("idea_embeddings", "idea_id")
        con.close()
        return ToolResult.success({"documents": doc_hits, "ideas": idea_hits})
    except Exception as exc:
        return ToolResult.failure("vector_query_error", str(exc))


def vector_stats(db_path: str) -> ToolResult:
    try:
        con = connect(Path(db_path))
        load_vec_extension(con)
        ensure_vec_tables(con)
        doc_count = con.execute("SELECT COUNT(*) AS c FROM doc_embeddings").fetchone()["c"]
        idea_count = con.execute("SELECT COUNT(*) AS c FROM idea_embeddings").fetchone()["c"]
        con.close()
        return ToolResult.success({"documents": int(doc_count), "ideas": int(idea_count)})
    except Exception as exc:
        return ToolResult.failure("vector_stats_error", str(exc))
