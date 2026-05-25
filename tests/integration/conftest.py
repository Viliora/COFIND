"""
DB integration + Flask app untuk tes API.

- Default: SQLite temp (terisolasi), memaksa COFIND_DB_BACKEND=sqlite.
- Opsional Postgres/Supabase: set COFIND_INTEGRATION_BACKEND=postgres dan
  DATABASE_URL atau SUPABASE_DB_URL (skema = schema_postgres.sql).

Jalankan: pytest -m integration
Jalankan ke Supabase: COFIND_INTEGRATION_BACKEND=postgres pytest tests/integration -m integration
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from typing import Optional

import pytest

import db_backend

_INTEGRATION_DB: Optional[str] = None


def _integration_backend() -> str:
    v = (os.getenv("COFIND_INTEGRATION_BACKEND") or "sqlite").strip().lower()
    if v in ("postgres", "postgresql", "supabase", "pg"):
        return "postgres"
    return "sqlite"


def _refresh_db_url_for_postgres() -> str:
    url = (os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or "").strip()
    db_backend.DATABASE_URL = url
    return url


def _schema_sql() -> str:
    return """
    CREATE TABLE users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT NOT NULL UNIQUE,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      is_admin INTEGER NOT NULL DEFAULT 0,
      is_active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT,
      updated_at TEXT
    );
    CREATE TABLE user_profiles (
      user_id INTEGER PRIMARY KEY,
      full_name TEXT,
      avatar_url TEXT,
      bio TEXT,
      phone TEXT,
      updated_at TEXT
    );
    CREATE TABLE sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      token TEXT NOT NULL,
      expires_at TEXT NOT NULL
    );
    CREATE TABLE coffee_shops (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      place_id TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      address TEXT,
      rating REAL,
      total_reviews INTEGER DEFAULT 0,
      photo_url TEXT,
      map_embed_url TEXT,
      latitude REAL,
      longitude REAL,
      created_at TEXT,
      updated_at TEXT
    );
    CREATE TABLE opening_hours (
      place_id TEXT PRIMARY KEY,
      hours_display TEXT,
      created_at TEXT,
      updated_at TEXT
    );
    CREATE TABLE reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      shop_id INTEGER NOT NULL,
      place_id TEXT NOT NULL,
      rating REAL NOT NULL,
      review_text TEXT,
      created_at TEXT,
      updated_at TEXT,
      rating_makanan INTEGER,
      rating_layanan INTEGER,
      rating_suasana INTEGER
    );
    CREATE TABLE review_photos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      review_id INTEGER NOT NULL,
      caption TEXT,
      image_data TEXT,
      created_at TEXT
    );
    CREATE TABLE favorites (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      shop_id INTEGER NOT NULL,
      place_id TEXT NOT NULL,
      added_at TEXT
    );
    CREATE TABLE want_to_visit (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      shop_id INTEGER NOT NULL,
      place_id TEXT NOT NULL,
      added_at TEXT
    );
    """


def _ensure_integration_database_sqlite() -> str:
    global _INTEGRATION_DB
    if _INTEGRATION_DB is not None:
        return _INTEGRATION_DB

    root = tempfile.mkdtemp(prefix="cofind_integration_")
    path = os.path.join(root, "cofind.db")
    _INTEGRATION_DB = path

    os.environ["COFIND_DB_BACKEND"] = "sqlite"
    for key in ("DATABASE_URL", "SUPABASE_DB_URL"):
        os.environ.pop(key, None)
    db_backend.DATABASE_URL = ""

    db_backend.DATABASE_PATH = path

    conn = sqlite3.connect(path)
    conn.executescript(_schema_sql())
    conn.commit()
    conn.close()
    return path


def _truncate_tables_sqlite() -> None:
    if not _INTEGRATION_DB:
        return
    conn = sqlite3.connect(_INTEGRATION_DB)
    conn.executescript(
        """
        DELETE FROM sessions;
        DELETE FROM review_photos;
        DELETE FROM reviews;
        DELETE FROM favorites;
        DELETE FROM want_to_visit;
        DELETE FROM opening_hours;
        DELETE FROM coffee_shops;
        DELETE FROM user_profiles;
        DELETE FROM users;
        """
    )
    conn.commit()
    conn.close()


def _truncate_tables_postgres() -> None:
    conn = db_backend.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            TRUNCATE TABLE
              review_likes,
              review_reports,
              review_photos,
              reviews,
              preference_suggestions,
              favorites,
              want_to_visit,
              opening_hours,
              coffee_shops,
              sessions,
              user_profiles,
              users
            RESTART IDENTITY CASCADE
            """
        )
        conn.commit()
    finally:
        conn.close()


def _truncate_tables() -> None:
    if _integration_backend() == "postgres":
        _truncate_tables_postgres()
    else:
        _truncate_tables_sqlite()


@pytest.fixture(scope="session")
def integration_app():
    if _integration_backend() == "postgres":
        url = _refresh_db_url_for_postgres()
        if not url:
            pytest.skip(
                "Integrasi Postgres: set DATABASE_URL atau SUPABASE_DB_URL "
                "(dan COFIND_INTEGRATION_BACKEND=postgres)."
            )
        os.environ["COFIND_DB_BACKEND"] = "postgres"
    else:
        _ensure_integration_database_sqlite()

    import app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app


@pytest.fixture
def client(integration_app):
    _truncate_tables()
    with integration_app.test_client() as c:
        yield c


@pytest.fixture
def sample_shop_id():
    """place_id konsisten untuk beberapa tes."""
    return "ChIJ_integration_test_place"


@pytest.fixture
def seed_coffee_shop(client, sample_shop_id):
    """Satu baris coffee_shops + jam buka (SQLite atau Postgres lewat db_backend)."""
    conn = db_backend.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO coffee_shops (
              place_id, name, address, rating, total_reviews,
              created_at, updated_at, map_embed_url, latitude, longitude
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sample_shop_id,
                "Kopi Integration",
                "Jl. Tes No. 1",
                4.5,
                3,
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:00",
                None,
                -6.2,
                106.8,
            ),
        )
        cur.execute(
            """
            INSERT INTO opening_hours (place_id, hours_display, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (sample_shop_id, "08:00–22:00", "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    return sample_shop_id
