"""
Script untuk mengupdate jam operasional (opening_hours) di database.
Menjalankan: python update_opening_hours.py
"""
from db_backend import get_connection

# (nama persis atau pola LIKE, jam operasional)
# Urutan: nama lebih spesifik dulu agar "Aming Coffee" tidak menimpa cabang lain
HOURS_DATA = [
    ("2818 Coffee Roasters", "Setiap hari 08.00–21.00."),
    ("5 CM Coffee and Eatery", "08.00–23.00."),
    ("Aming Coffee Ilham", "06.00–00.00."),
    ("Aming Coffee Podomoro", "07.00–02.00."),
    ("Aming Coffee Siantan", "07.00–00.00."),
    ("Aming Coffee", "06.00–23.00."),
    ("CW Coffee Tanjung Raya", "24 jam."),
    ("Disela Coffee & Roastery", "08.00–22.30."),
    ("Haruna Cafe", "07.00–23.30."),
    ("Heim Coffee", "07.00–23.00."),
    ("NUTRICULA COFFEE", "06.00–22.00."),
    ("Osamu Coffee", "09.00–23.00."),
    ("Rumah Kita Coffee & Eatery", "07.00–23.00."),
    ("Seremoni Coffee", "08.00–23.00."),
    ("Sidedoors Coffee Shop", "09.00–23.00."),
]


def update_opening_hours():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        updated = 0
        for name_pattern, hours in HOURS_DATA:
            if name_pattern == "Aming Coffee":
                cursor.execute(
                    "SELECT place_id, name FROM coffee_shops WHERE LOWER(name) = LOWER(?)",
                    (name_pattern,),
                )
            else:
                cursor.execute(
                    "SELECT place_id, name FROM coffee_shops WHERE LOWER(name) LIKE LOWER(?)",
                    (f"%{name_pattern}%",),
                )
            row = cursor.fetchone()
            if row:
                place_id, actual_name = row[0], row[1]
                cursor.execute(
                    "UPDATE opening_hours SET hours_display = ?, updated_at = CURRENT_TIMESTAMP WHERE place_id = ?",
                    (hours, place_id),
                )
                if cursor.rowcount:
                    updated += 1
                    print(f"[OK] {actual_name}: {hours}")
            else:
                print(f"[NOT FOUND] {name_pattern}")
        conn.commit()
        print(f"\n[INFO] Updated {updated} coffee shops.")
    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    update_opening_hours()
