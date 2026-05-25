"""
Unit test untuk favorites_utils (SQLite terisolasi, tanpa Postgres / cofind.db produksi).
"""
import sqlite3

import pytest

import favorites_utils as fav


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE coffee_shops (
            id INTEGER PRIMARY KEY,
            place_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            address TEXT,
            rating REAL,
            total_reviews INTEGER DEFAULT 0
        );
        CREATE TABLE favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            shop_id INTEGER NOT NULL,
            place_id TEXT NOT NULL,
            added_at TEXT
        );
        """
    )
    conn.commit()


@pytest.fixture
def fav_sqlite(monkeypatch, tmp_path):
    """Patch get_db_connection agar memakai SQLite file sementara."""
    db_file = tmp_path / "test_favorites.db"

    def get_conn():
        return sqlite3.connect(str(db_file))

    c0 = sqlite3.connect(str(db_file))
    _init_schema(c0)
    c0.close()

    monkeypatch.setattr(fav, "get_db_connection", get_conn)
    yield db_file


def test_get_co_favorited_shops_empty_when_no_favorites(fav_sqlite):
    out = fav.get_co_favorited_shops("ChIJ_any_place", limit=8)
    assert out["success"] is True
    assert out["shops"] == []


def test_get_co_favorited_shops_orders_by_co_occurrence(fav_sqlite):
    conn = fav.get_db_connection()
    cur = conn.cursor()
    # Tiga toko
    cur.executemany(
        "INSERT INTO coffee_shops (id, place_id, name, address, rating, total_reviews) VALUES (?,?,?,?,?,?)",
        [
            (1, "place_A", "Kopi A", "Jl A", 4.5, 10),
            (2, "place_B", "Kopi B", "Jl B", 4.6, 20),
            (3, "place_C", "Kopi C", "Jl C", 4.4, 5),
        ],
    )
    # User 1 & 3: suka A dan B. User 2: suka A dan C.
    # Co-favorit untuk A: B (2 user), C (1 user) → B dulu.
    rows = [
        (1, 1, "place_A"),
        (1, 2, "place_B"),
        (2, 1, "place_A"),
        (2, 3, "place_C"),
        (3, 1, "place_A"),
        (3, 2, "place_B"),
    ]
    cur.executemany(
        "INSERT INTO favorites (user_id, shop_id, place_id, added_at) VALUES (?,?,?,datetime('now'))",
        rows,
    )
    conn.commit()
    conn.close()

    out = fav.get_co_favorited_shops("place_A", limit=8)
    assert out["success"] is True
    pids = [s["place_id"] for s in out["shops"]]
    assert "place_A" not in pids
    assert pids[0] == "place_B"
    assert "place_C" in pids


def test_get_co_favorited_shops_excludes_viewer_user_id(fav_sqlite):
    """Hanya pola user lain: exclude_user_id tidak boleh jadi sumber f1."""
    conn = fav.get_db_connection()
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO coffee_shops (id, place_id, name, address, rating, total_reviews) VALUES (?,?,?,?,?,?)",
        [
            (1, "pA", "Kopi A", "Jl A", 4.5, 1),
            (2, "pB", "Kopi B", "Jl B", 4.0, 1),
            (3, "pC", "Kopi C", "Jl C", 4.2, 1),
        ],
    )
    # Hanya user 5 yang punya A+B; user 6 punya A+C
    cur.executemany(
        "INSERT INTO favorites (user_id, shop_id, place_id, added_at) VALUES (?,?,?,datetime('now'))",
        [
            (5, 1, "pA"),
            (5, 2, "pB"),
            (6, 1, "pA"),
            (6, 3, "pC"),
        ],
    )
    conn.commit()
    conn.close()

    out_all = fav.get_co_favorited_shops("pA", limit=8)
    pids_all = [s["place_id"] for s in out_all["shops"]]
    assert "pB" in pids_all and "pC" in pids_all

    out_ex = fav.get_co_favorited_shops("pA", limit=8, exclude_user_id=5)
    pids_ex = [s["place_id"] for s in out_ex["shops"]]
    assert "pB" not in pids_ex
    assert pids_ex[0] == "pC"


def test_get_co_favorited_shops_respects_limit(fav_sqlite):
    conn = fav.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO coffee_shops (id, place_id, name, address, rating, total_reviews) VALUES (10,'p_root','Root','x',4.5,1)"
    )
    for i in range(1, 6):
        cur.execute(
            "INSERT INTO coffee_shops (id, place_id, name, address, rating, total_reviews) VALUES (?,?,?,?,?,?)",
            (i, f"extra_{i}", f"E{i}", "addr", 4.0, 1),
        )
    for uid in range(1, 6):
        cur.execute(
            "INSERT INTO favorites (user_id, shop_id, place_id, added_at) VALUES (?,10,'p_root',datetime('now'))",
            (uid,),
        )
        cur.execute(
            "INSERT INTO favorites (user_id, shop_id, place_id, added_at) VALUES (?,?,?,datetime('now'))",
            (uid, uid, f"extra_{uid}"),
        )
    conn.commit()
    conn.close()

    out = fav.get_co_favorited_shops("p_root", limit=2)
    assert out["success"] is True
    assert len(out["shops"]) == 2


def test_add_favorite_uses_canonical_place_id(fav_sqlite):
    conn = fav.get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO coffee_shops (id, place_id, name, address, rating, total_reviews) VALUES (1,' canon ','Canon','x',4.0,1)"
    )
    conn.commit()
    conn.close()

    out = fav.add_favorite(1, "canon")
    assert out["success"] is True
    conn = fav.get_db_connection()
    row = conn.execute("SELECT place_id FROM favorites WHERE user_id=1").fetchone()
    conn.close()
    assert row is not None
    assert row[0].strip() == "canon"
