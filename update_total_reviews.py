"""
Update total_reviews di coffee_shops sesuai data yang benar (Google Maps).
Menjalankan: python update_total_reviews.py
"""
import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

# Nama coffee shop (persis seperti di DB) -> total ulasan yang benar
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
    "Osamu Coffee": 0,  # ulasan belum tersedia / tidak terdaftar di Google Maps
    "Rumah Kita Coffee & Eatery": 82,
    "Seremoni Coffee": 80,
    "Sidedoors Coffee Shop": 361,
    # CW Coffee Tanjung Raya tidak ada di list user - tidak di-update (tetap nilai lama)
}

def main():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(coffee_shops)")
    columns = [row[1] for row in cursor.fetchall()]
    has_total_reviews = 'total_reviews' in columns
    has_user_ratings = 'user_ratings_total' in columns
    if not has_total_reviews and not has_user_ratings:
        print("[ERROR] Kolom total_reviews atau user_ratings_total tidak ada.")
        conn.close()
        return

    updated = 0
    for name, total in CORRECT_TOTAL_REVIEWS.items():
        if has_total_reviews and has_user_ratings:
            cursor.execute(
                "UPDATE coffee_shops SET total_reviews = ?, user_ratings_total = ? WHERE name = ?",
                (total, total, name)
            )
        elif has_total_reviews:
            cursor.execute("UPDATE coffee_shops SET total_reviews = ? WHERE name = ?", (total, name))
        else:
            cursor.execute("UPDATE coffee_shops SET user_ratings_total = ? WHERE name = ?", (total, name))
        if cursor.rowcount > 0:
            print(f"  [OK] {name} -> {total} ulasan")
            updated += 1
        else:
            print(f"  [SKIP] Tidak ditemukan: {name}")

    conn.commit()
    print(f"\nTotal di-update: {updated} coffee shop")
    conn.close()

if __name__ == "__main__":
    main()
