"""
Tambah kolom rating kategori (makanan, layanan, suasana) pada reviews
dan buat tabel review_photos untuk foto/gambar dengan keterangan opsional.
"""

import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

def migrate():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        # Cek kolom yang sudah ada di reviews
        cursor.execute("PRAGMA table_info(reviews)")
        columns = [row[1] for row in cursor.fetchall()]

        for col, default in [
            ('rating_makanan', None),
            ('rating_layanan', None),
            ('rating_suasana', None)
        ]:
            if col not in columns:
                cursor.execute(f"ALTER TABLE reviews ADD COLUMN {col} INTEGER")
                print(f"[INFO] Added column reviews.{col}")

        # Tabel review_photos: foto/gambar dengan keterangan opsional
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                caption TEXT,
                image_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
            )
        """)
        print("[INFO] Table review_photos created or already exists.")
        conn.commit()
    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
