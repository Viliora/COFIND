#!/usr/bin/env python3
"""
Complete SQLite database migration - All tables including auth, profiles, reviews, favorites
"""
import sqlite3
import os
from datetime import datetime
import hashlib

def create_tables():
    """Create all necessary tables"""
    db_path = os.path.join(os.path.dirname(__file__), 'cofind.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. USERS table (for authentication)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    print("✅ Created users table")
    
    # 2. USER_PROFILES table (extended user info)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            full_name TEXT,
            bio TEXT,
            avatar_url TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    print("✅ Created user_profiles table")
    
    # 3. SESSIONS table (for session management)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    print("✅ Created sessions table")
    
    # 4. REVIEWS table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            shop_id INTEGER NOT NULL,
            place_id TEXT NOT NULL,
            rating REAL NOT NULL CHECK(rating >= 1 AND rating <= 5),
            review_text TEXT,
            keywords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (shop_id) REFERENCES coffee_shops(id) ON DELETE CASCADE,
            UNIQUE(user_id, place_id)
        )
    ''')
    print("✅ Created reviews table")
    
    # 5. FAVORITES table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            shop_id INTEGER NOT NULL,
            place_id TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (shop_id) REFERENCES coffee_shops(id) ON DELETE CASCADE,
            UNIQUE(user_id, place_id)
        )
    ''')
    print("✅ Created favorites table")
    
    # 6. WANT_TO_VISIT table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS want_to_visit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            shop_id INTEGER NOT NULL,
            place_id TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (shop_id) REFERENCES coffee_shops(id) ON DELETE CASCADE,
            UNIQUE(user_id, place_id)
        )
    ''')
    print("✅ Created want_to_visit table")
    
    # 7. REVIEW_REPORTS table (for admin moderation)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS review_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id INTEGER NOT NULL,
            report_reason TEXT NOT NULL,
            report_text TEXT,
            reported_by_user_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            admin_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,
            FOREIGN KEY (reported_by_user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    print("✅ Created review_reports table")
    
    conn.commit()
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviews_place_id ON reviews(place_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_want_to_visit_user_id ON want_to_visit(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)')
    
    print("✅ Created indexes")
    
    # Check if coffee_shops table exists, if not create it
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coffee_shops'")
    if not cursor.fetchone():
        print("❌ coffee_shops table not found - run migrate_to_sqlite.py first!")
        return False
    
    conn.commit()
    conn.close()
    
    print("\n" + "="*60)
    print("✅ Database schema complete!")
    print("="*60)
    return True

if __name__ == '__main__':
    create_tables()
