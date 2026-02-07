"""Tabel review_likes untuk fitur like pada review."""

import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

def migrate():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS review_likes (
                user_id INTEGER NOT NULL,
                review_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, review_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        print("[INFO] Table review_likes created or already exists.")
    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
