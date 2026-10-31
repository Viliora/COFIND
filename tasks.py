from __future__ import annotations

from celery_app import celery_app


@celery_app.task(name="cofind.embed_review_task")
def embed_review_task(review_id: int):
    """Backfill/update satu baris review_embeddings dari teks review di DB."""
    from db_backend import get_connection
    from review_embedding_store import upsert_review_embedding, use_pgvector_store

    if not use_pgvector_store():
        return {"status": "skipped", "reason": "not_pgvector"}
    rid = int(review_id)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT review_text FROM reviews WHERE id = ?", (rid,))
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return {"status": "error", "message": "review not found", "review_id": rid}
    text = row[0] or ""
    ok = upsert_review_embedding(rid, text)
    if not ok:
        return {"status": "error", "message": "upsert failed", "review_id": rid}
    return {"status": "success", "review_id": rid}
