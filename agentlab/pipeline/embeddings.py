from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Sequence

from agentlab.db.db import with_retry

DEFAULT_EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384


def load_vec_extension(con) -> None:
    try:
        import sqlite_vec
    except Exception as exc:  # pragma: no cover - runtime import
        raise RuntimeError("sqlite-vec is not installed. pip install sqlite-vec") from exc
    con.enable_load_extension(True)
    sqlite_vec.load(con)


def ensure_vec_tables(con) -> None:
    con.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS doc_embeddings USING vec0(embedding float[{EMBED_DIM}], doc_id TEXT)"
    )
    con.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS idea_embeddings USING vec0(embedding float[{EMBED_DIM}], idea_id TEXT)"
    )


def serialize_vector(vec: Sequence[float]):
    try:
        import sqlite_vec
        if hasattr(sqlite_vec, "serialize"):
            return sqlite_vec.serialize(vec)
    except Exception:
        pass
    try:
        from array import array
        return array("f", vec).tobytes()
    except Exception:
        return vec


@lru_cache(maxsize=2)
def get_model(model_name: str = DEFAULT_EMBED_MODEL):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(model_name)


def batch_encode(texts: Sequence[str], model_name: str = DEFAULT_EMBED_MODEL) -> list[list[float]]:
    model = get_model(model_name)
    return model.encode(list(texts), normalize_embeddings=True).tolist()


def upsert_embeddings(con, *, table: str, id_field: str, ids: Sequence[str], vectors: Sequence[Sequence[float]]) -> None:
    for item_id, vec in zip(ids, vectors):
        with_retry(lambda: con.execute(f"DELETE FROM {table} WHERE {id_field}=?", (item_id,)))
        with_retry(
            lambda: con.execute(
                f"INSERT INTO {table} (embedding, {id_field}) VALUES (?, ?)",
                (serialize_vector(vec), item_id),
            )
        )
