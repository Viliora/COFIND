#!/usr/bin/env python3
"""
Migrate coffee shops data dari Supabase ke SQLite
Run: python migrate_to_sqlite.py
"""
import sqlite3
import os
from datetime import datetime

# Data 15 coffee shops yang di-load dari Supabase sebelumnya
COFFEE_SHOPS = [
    {"name": "Kopi Toko Seni", "address": "Jl. Sultan Abdurrahman, Pontianak", "rating": 4.6, "reviews": 128, "place_id": "ChIJyRLXBlJYHS4RWNj0yvAvSAQ"},
    {"name": "Kedai Kopi Rengganis", "address": "Jl. Ahmad Yani, Pontianak", "rating": 4.5, "reviews": 95, "place_id": "ChIJ9RWUkaZZHS4RYeuZOYAMQ-4"},
    {"name": "Coffee Square", "address": "Jl. Gajah Mada, Pontianak", "rating": 4.4, "reviews": 87, "place_id": "ChIJ6fOdOEBZHS4RcV3VfZzhYx0"},
    {"name": "Kopi Nusantara", "address": "Jl. Diponegoro, Pontianak", "rating": 4.3, "reviews": 76, "place_id": "ChIJhx6zl0BZHS4RGNla_oPoIJ0"},
    {"name": "Warung Kopi Aming", "address": "Jl. Sultan Abdurrahman, Pontianak", "rating": 4.5, "reviews": 112, "place_id": "ChIJPa6swGtZHS4RrbIlRvgBgok"},
    {"name": "Java Junction", "address": "Jl. Imam Bonjol, Pontianak", "rating": 4.2, "reviews": 65, "place_id": "ChIJDcJgropZHS4RKuh8s52jy9U"},
    {"name": "Espresso Bar", "address": "Jl. Tanjungpura, Pontianak", "rating": 4.1, "reviews": 54, "place_id": "ChIJIRuUuwNZHS4RrhnXINPqQQ4"},
    {"name": "Kedai Kopi Pintar", "address": "Jl. Singkawang, Pontianak", "rating": 4.3, "reviews": 81, "place_id": "ChIJC3_RpddZHS4RMiDp7-6TemY"},
    {"name": "Kopi Suara", "address": "Jl. Veteran, Pontianak", "rating": 4.4, "reviews": 93, "place_id": "ChIJE8-LfABZHS4R_MsSOwiHNL8"},
    {"name": "The Daily Grind", "address": "Jl. Merdeka, Pontianak", "rating": 4.2, "reviews": 70, "place_id": "ChIJBVWfsoFZHS4Rakb44yanMjs"},
    {"name": "Artisan Coffee House", "address": "Jl. Cendana, Pontianak", "rating": 4.5, "reviews": 105, "place_id": "ChIJG-xwV2ZZHS4R0WyGi5bbvoM"},
    {"name": "Kopi Santai", "address": "Jl. Hasanuddin, Pontianak", "rating": 4.0, "reviews": 48, "place_id": "ChIJ4U6K9hdZHS4RKE7QPIKbn4Y"},
    {"name": "Black Coffee", "address": "Jl. Teuku Umar, Pontianak", "rating": 4.3, "reviews": 82, "place_id": "ChIJ71m2hZZZHS4RrOgKJYP_7zw"},
    {"name": "Roastery & Brew", "address": "Jl. Kartini, Pontianak", "rating": 4.4, "reviews": 99, "place_id": "ChIJKX36yixZHS4ROQfX-hNWhj0"},
    {"name": "Kedai Kopi 99", "address": "Jl. Pahlawan, Pontianak", "rating": 4.1, "reviews": 59, "place_id": "ChIJpVctpWBZHS4RdUbSlT-pSl8"},
]

def create_database():
    """Create SQLite database dan tables"""
    db_path = os.path.join(os.path.dirname(__file__), 'cofind.db')
    
    # Delete existing database untuk fresh start
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"[✓] Removed existing database")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create coffee_shops table
    cursor.execute('''
        CREATE TABLE coffee_shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            rating REAL DEFAULT 0,
            user_ratings_total INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("[✓] Created coffee_shops table")
    
    # Insert data
    for shop in COFFEE_SHOPS:
        cursor.execute('''
            INSERT INTO coffee_shops (place_id, name, address, rating, user_ratings_total)
            VALUES (?, ?, ?, ?, ?)
        ''', (shop['place_id'], shop['name'], shop['address'], shop['rating'], shop['reviews']))
    
    conn.commit()
    print(f"[✓] Inserted {len(COFFEE_SHOPS)} coffee shops")
    
    # Verify
    cursor.execute('SELECT COUNT(*) FROM coffee_shops')
    count = cursor.fetchone()[0]
    print(f"[✓] Verified: {count} shops in database")
    
    conn.close()
    print(f"[✓] Database created at: {db_path}")

if __name__ == '__main__':
    create_database()
    print("\n✅ Migration complete! Ready to update app.py")
