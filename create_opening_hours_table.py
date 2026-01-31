"""
Script untuk membuat tabel opening_hours (jam operasional) di database.
Satu baris per coffee shop: place_id, hours_display (teks tampilan).
"""

import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

def create_opening_hours_table():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opening_hours (
                place_id TEXT PRIMARY KEY,
                hours_display TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (place_id) REFERENCES coffee_shops(place_id)
            )
        """)
        conn.commit()
        print("[INFO] Table opening_hours created successfully.")

        # Cek apakah sudah ada data
        cursor.execute("SELECT COUNT(*) FROM opening_hours")
        count = cursor.fetchone()[0]
        if count == 0:
            # Insert placeholder untuk semua coffee shop (bisa diisi manual nanti)
            cursor.execute("SELECT place_id, name FROM coffee_shops")
            shops = cursor.fetchall()
            for place_id, name in shops:
                cursor.execute(
                    "INSERT OR IGNORE INTO opening_hours (place_id, hours_display) VALUES (?, ?)",
                    (place_id, "Jam operasional belum diisi")
                )
            conn.commit()
            print(f"[INFO] Inserted placeholder for {len(shops)} coffee shops.")
        else:
            print(f"[INFO] opening_hours already has {count} row(s).")
    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_opening_hours_table()
