"""
Update total_reviews di coffee_shops sesuai data yang benar (Google Maps).
Menjalankan: python update_total_reviews.py
"""
from db_backend import get_connection, use_postgres

CORRECT_TOTAL_REVIEWS = {
    "2818 Coffee Roasters": 79,
    "5 CM Coffee and Eatery": 746,
    "Aming Coffee": 4000,
    "Aming Coffee Ilham": 1372,
    "Aming Coffee Podomoro": 3026,
    "Aming Coffee Siantan": 521,
    "Disela Coffee & Roastery": 77,
    "Haruna Cafe": 621,
    "Heim Coffee": 131,
    "NUTRICULA COFFEE": 178,
    "Osamu Coffee": 0,
    "Rumah Kita Coffee & Eatery": 82,
    "Seremoni Coffee": 80,
    "Sidedoors Coffee Shop": 361,
}


def _column_exists(conn, table, column):
    cur = conn.cursor()
    if use_postgres():
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = ? AND column_name = ?",
            (table, column),
        )
        return cur.fetchone() is not None
    cur.execute(f"PRAGMA table_info({table})")
    return any(str(row[1]).lower() == column.lower() for row in cur.fetchall())


def main():
    conn = get_connection()
    cur = conn.cursor()

    has_total_reviews = _column_exists(conn, "coffee_shops", "total_reviews")
    has_user_ratings = _column_exists(conn, "coffee_shops", "user_ratings_total")
    if not has_total_reviews and not has_user_ratings:
        print("[ERROR] Kolom total_reviews atau user_ratings_total tidak ada.")
        conn.close()
        return

    updated = 0
    for name, total in CORRECT_TOTAL_REVIEWS.items():
        if has_total_reviews and has_user_ratings:
            cur.execute(
                "UPDATE coffee_shops SET total_reviews = ?, user_ratings_total = ? WHERE name = ?",
                (total, total, name),
            )
        elif has_total_reviews:
            cur.execute(
                "UPDATE coffee_shops SET total_reviews = ? WHERE name = ?",
                (total, name),
            )
        else:
            cur.execute(
                "UPDATE coffee_shops SET user_ratings_total = ? WHERE name = ?",
                (total, name),
            )
        if cur.rowcount > 0:
            print(f"  [OK] {name} -> {total} ulasan")
            updated += 1
        else:
            print(f"  [SKIP] Tidak ditemukan: {name}")

    conn.commit()
    print(f"\nTotal di-update: {updated} coffee shop")
    conn.close()


if __name__ == "__main__":
    main()
