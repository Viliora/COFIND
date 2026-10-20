"""
Hapus ulasan manual (cofind) yang teksnya sama dengan ulasan google_places
pada place_id yang sama. Sisakan yang dari fetch API.
"""
from __future__ import annotations

import json
import sys

from dotenv import load_dotenv

load_dotenv()

from db_backend import get_connection

GOOGLE = "google_places"
COFIND = "cofind"


def normalize_text(text: str | None) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def find_duplicate_manual_ids(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, place_id, review_source, review_text, user_id
        FROM reviews
        ORDER BY place_id, id
        """
    )
    rows = cur.fetchall() or []
    google_texts_by_place: dict[str, set[str]] = {}
    parsed = []
    for row in rows:
        if isinstance(row, dict):
            r = row
        else:
            r = {
                "id": row[0],
                "place_id": row[1],
                "review_source": row[2],
                "review_text": row[3],
                "user_id": row[4],
            }
        parsed.append(r)
        src = (r.get("review_source") or COFIND).strip()
        if src != GOOGLE:
            continue
        pid = str(r.get("place_id") or "")
        txt = normalize_text(r.get("review_text"))
        if pid and txt:
            google_texts_by_place.setdefault(pid, set()).add(txt)

    to_delete: list[dict] = []
    for r in parsed:
        src = (r.get("review_source") or COFIND).strip()
        if src != COFIND:
            continue
        pid = str(r.get("place_id") or "")
        txt = normalize_text(r.get("review_text"))
        if pid and txt and txt in google_texts_by_place.get(pid, set()):
            to_delete.append(r)
    return to_delete


def delete_reviews(conn, review_ids: list[int]) -> None:
    if not review_ids:
        return
    cur = conn.cursor()
    placeholders = ",".join("?" * len(review_ids))
    for table in ("review_likes", "review_photos", "review_reports", "review_embeddings"):
        try:
            cur.execute(
                f"DELETE FROM {table} WHERE review_id IN ({placeholders})",
                tuple(review_ids),
            )
        except Exception as err:
            if "does not exist" not in str(err).lower():
                raise
    cur.execute(
        f"DELETE FROM reviews WHERE id IN ({placeholders})",
        tuple(review_ids),
    )
    conn.commit()


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    conn = get_connection()
    try:
        dups = find_duplicate_manual_ids(conn)
    finally:
        conn.close()

    print(json.dumps({"duplicate_manual_count": len(dups), "dry_run": dry_run}, ensure_ascii=False))
    for d in dups:
        preview = (d.get("review_text") or "")[:100].replace("\n", " ")
        print(
            f"  id={d['id']} place_id={d['place_id']} user_id={d.get('user_id')} | {preview}"
        )

    if dry_run or not dups:
        return 0

    ids = [int(d["id"]) for d in dups]
    conn = get_connection()
    try:
        delete_reviews(conn, ids)
    finally:
        conn.close()
    print(f"Deleted {len(ids)} manual duplicate review(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
