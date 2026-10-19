"""
Persist review dense embeddings in Supabase pgvector (optional via COFIND_EMBEDDING_STORE).
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from db_backend import get_connection
from hybrid_retrieval import drop_rejection_sentences
from logging_config import get_logger
from semantic_match import clean_clause_for_embedding, embed_texts, model_name

logger = get_logger("semantic")

PGVECTOR_DIM = int(os.getenv("COFIND_PGVECTOR_DIM", "384"))


def embedding_store_mode() -> str:
    return (os.getenv("COFIND_EMBEDDING_STORE") or "cache").strip().lower()


def use_pgvector_store() -> bool:
    return embedding_store_mode() == "pgvector"


def canonical_embedding_text(review_text: str) -> str:
    return clean_clause_for_embedding(drop_rejection_sentences(review_text or ""))


def source_text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _vector_literal(vec: Sequence[float]) -> str:
    parts = [f"{float(x):.8f}" for x in vec]
    return "[" + ",".join(parts) + "]"


def _parse_vector_text(raw: object) -> Optional[np.ndarray]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s.startswith("[") or not s.endswith("]"):
        return None
    inner = s[1:-1].strip()
    if not inner:
        return None
    try:
        vals = [float(x) for x in inner.split(",")]
    except ValueError:
        return None
    if len(vals) != PGVECTOR_DIM:
        return None
    return np.asarray(vals, dtype=np.float32)


def upsert_review_embedding(review_id: int, review_text: str) -> bool:
    if not use_pgvector_store():
        return False
    canon = canonical_embedding_text(review_text)
    if len(canon) < 6:
        delete_review_embedding(review_id)
        return False
    vectors = embed_texts([canon])
    vec = vectors.get(canon)
    if vec is None:
        return False
    arr = np.asarray(vec, dtype=np.float32).reshape(-1)
    if arr.size != PGVECTOR_DIM:
        logger.warning("review %s embedding dim %s != %s", review_id, arr.size, PGVECTOR_DIM)
        return False
    text_hash = source_text_hash(canon)
    model_id = model_name()
    literal = _vector_literal(arr)
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    try:
        cur = conn.cursor()
        sql = (
            "INSERT INTO review_embeddings (review_id, embedding, model_id, source_text_hash, updated_at) "
            "VALUES (%s, %s::vector, %s, %s, %s) "
            "ON CONFLICT (review_id) DO UPDATE SET "
            "embedding = EXCLUDED.embedding, model_id = EXCLUDED.model_id, "
            "source_text_hash = EXCLUDED.source_text_hash, updated_at = EXCLUDED.updated_at"
        )
        cur.execute(sql, (review_id, literal, model_id, text_hash, now))
        conn.commit()
        return True
    except Exception as err:
        conn.rollback()
        logger.warning("upsert_review_embedding(%s) gagal: %s", review_id, err)
        return False
    finally:
        conn.close()


def delete_review_embedding(review_id: int) -> None:
    if not use_pgvector_store():
        return
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM review_embeddings WHERE review_id = %s", (review_id,))
        conn.commit()
    except Exception as err:
        conn.rollback()
        logger.debug("delete_review_embedding(%s): %s", review_id, err)
    finally:
        conn.close()


def fetch_embeddings(review_ids: Sequence[int]) -> Dict[int, Tuple[np.ndarray, str, str]]:
    ids = [int(i) for i in review_ids if i is not None]
    if not ids or not use_pgvector_store():
        return {}
    placeholders = ",".join(["%s"] * len(ids))
    conn = get_connection()
    try:
        cur = conn.cursor()
        q = (
            "SELECT review_id, embedding::text, source_text_hash, model_id "
            f"FROM review_embeddings WHERE review_id IN ({placeholders})"
        )
        cur.execute(q, tuple(ids))
        out: Dict[int, Tuple[np.ndarray, str, str]] = {}
        for row in cur.fetchall():
            rid, emb_text, thash, mid = row[0], row[1], row[2], row[3]
            vec = _parse_vector_text(emb_text)
            if vec is not None:
                out[int(rid)] = (vec, str(thash or ""), str(mid or ""))
        return out
    finally:
        conn.close()


def sync_review_embedding_after_write(review_id: int, review_text: str) -> None:
    if not use_pgvector_store():
        return
    try:
        upsert_review_embedding(review_id, review_text)
    except Exception as err:
        logger.warning("sync_review_embedding_after_write(%s): %s", review_id, err)


def embedding_async_enabled() -> bool:
    raw = (os.getenv("COFIND_EMBEDDING_ASYNC") or "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def schedule_review_embedding_after_write(review_id: int, review_text: str) -> None:
    """Sync upsert atau queue Celery bila COFIND_EMBEDDING_ASYNC=true."""
    if not use_pgvector_store():
        return
    if embedding_async_enabled():
        try:
            from tasks import embed_review_task

            embed_review_task.delay(int(review_id))
            return
        except Exception as err:
            logger.warning(
                "schedule_review_embedding async(%s) gagal, sync: %s",
                review_id,
                err,
            )
    sync_review_embedding_after_write(review_id, review_text)


def fetch_embedding_coverage_stats() -> Dict[str, Any]:
    """Hitung coverage review_embeddings vs ulasan yang bisa di-embed."""
    store_mode = embedding_store_mode()
    model_id = model_name()
    embedded_count = 0
    latest_updated_at = None
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM review_embeddings")
        row = cur.fetchone()
        embedded_count = int(row[0] if row else 0)
        cur.execute("SELECT MAX(updated_at) FROM review_embeddings")
        row = cur.fetchone()
        if row and row[0] is not None:
            latest_updated_at = str(row[0])
        cur.execute("SELECT review_text FROM reviews WHERE review_text IS NOT NULL")
        review_rows = cur.fetchall()
    finally:
        conn.close()

    embeddable_count = 0
    for (text,) in review_rows:
        if len(canonical_embedding_text(text or "")) >= 6:
            embeddable_count += 1
    ratio = (
        float(embedded_count) / float(embeddable_count)
        if embeddable_count > 0
        else None
    )
    return {
        "store_mode": store_mode,
        "model_id": model_id,
        "pgvector_dim": PGVECTOR_DIM,
        "embeddable_count": embeddable_count,
        "embedded_count": embedded_count,
        "coverage_ratio": round(ratio, 4) if ratio is not None else None,
        "coverage_percent": round(100.0 * ratio, 1) if ratio is not None else None,
        "latest_updated_at": latest_updated_at,
    }


def ann_search_reviews(
    query_vector: np.ndarray,
    place_ids: Sequence[str],
    *,
    limit: int = 300,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    ANN cosine scoped ke place_id (Fase 1). Butuh pgvector + index HNSW.
    """
    telemetry: Dict[str, Any] = {
        "rows_returned": 0,
        "ann_ms": 0.0,
        "ann_top_k": int(limit),
        "error": None,
    }
    if not use_pgvector_store():
        telemetry["error"] = "not_pgvector"
        return [], telemetry

    pids = [str(p).strip() for p in (place_ids or []) if str(p).strip()]
    if not pids or query_vector is None:
        telemetry["error"] = "no_input"
        return [], telemetry

    arr = np.asarray(query_vector, dtype=np.float32).reshape(-1)
    if arr.size != PGVECTOR_DIM:
        telemetry["error"] = f"bad_dim_{arr.size}"
        return [], telemetry

    literal = _vector_literal(arr)
    cap = max(1, min(int(limit), 5000))
    placeholders = ",".join(["%s"] * len(pids))
    sql = (
        "SELECT re.review_id, r.place_id, (re.embedding <=> %s::vector) AS distance "
        "FROM review_embeddings re "
        "INNER JOIN reviews r ON r.id = re.review_id "
        f"WHERE r.place_id IN ({placeholders}) "
        "ORDER BY re.embedding <=> %s::vector "
        "LIMIT %s"
    )
    params: List[Any] = [literal, *pids, literal, cap]
    t0 = time.perf_counter()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        out: List[Dict[str, Any]] = []
        for rid, pid, dist in cur.fetchall():
            distance = float(dist or 0.0)
            similarity = max(0.0, min(1.0, 1.0 - distance))
            out.append(
                {
                    "review_id": int(rid),
                    "place_id": str(pid),
                    "similarity": similarity,
                }
            )
        telemetry["rows_returned"] = len(out)
        return out, telemetry
    except Exception as err:
        telemetry["error"] = str(err)[:200]
        logger.warning("ann_search_reviews gagal: %s", err)
        return [], telemetry
    finally:
        conn.close()
        telemetry["ann_ms"] = round((time.perf_counter() - t0) * 1000, 1)
