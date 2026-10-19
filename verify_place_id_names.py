"""Bandingkan coffee_shops DB vs Google Text Search + nama Place Details."""
from __future__ import annotations

import json
import re
import time
from difflib import SequenceMatcher

import requests
from dotenv import load_dotenv

load_dotenv()

from fetch_google_places_reviews import (
    _resolve_api_key,
    build_search_query,
    fetch_coffee_shops_from_db,
    legacy_place_details,
    legacy_text_search,
)


def norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return " ".join(s.split())


def name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def main() -> None:
    api_key, _ = _resolve_api_key()
    session = requests.Session()
    shops = fetch_coffee_shops_from_db()
    rows = []
    mismatches = []

    for i, shop in enumerate(shops):
        if i > 0:
            time.sleep(0.35)
        db_id = str(shop.get("place_id") or "")
        db_name = str(shop.get("name") or "")
        address = str(shop.get("address") or "")
        q = build_search_query(db_name, address)
        hit = legacy_text_search(session, api_key, q) or {}
        search_id = hit.get("place_id") or ""
        search_name = hit.get("name") or ""

        details_name = ""
        if db_id:
            det = legacy_place_details(session, api_key, db_id)
            time.sleep(0.2)
            if not det.get("_error"):
                details_name = det.get("name") or ""

        sim_search = name_similarity(db_name, search_name) if search_name else 0.0
        sim_details = name_similarity(db_name, details_name) if details_name else 0.0
        id_match_db_search = db_id == search_id if search_id else None

        status = "sesuai"
        recommended_id = db_id
        note = ""

        if not search_id:
            status = "tidak_ditemukan_search"
            note = "Text Search tidak mengembalikan hasil"
        elif db_id != search_id:
            status = "place_id_beda"
            recommended_id = search_id
            note = f"DB={db_id} vs Search={search_id}"
        elif sim_search < 0.55 and sim_details < 0.55:
            status = "nama_kurang_cocok"
            note = f"similarity search={sim_search:.2f} details={sim_details:.2f}"

        row = {
            "db_name": db_name,
            "db_place_id": db_id,
            "search_query": q,
            "google_search_place_id": search_id,
            "google_search_name": search_name,
            "google_details_name_for_db_id": details_name,
            "name_sim_vs_search": round(sim_search, 3),
            "name_sim_vs_details": round(sim_details, 3),
            "status": status,
            "recommended_place_id": recommended_id if status != "sesuai" else db_id,
            "note": note,
        }
        rows.append(row)
        if status != "sesuai":
            mismatches.append(row)

    print(json.dumps({"total": len(rows), "mismatch_count": len(mismatches), "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
