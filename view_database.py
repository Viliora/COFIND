#!/usr/bin/env python3
"""
Simple SQLite Database Viewer - Console Version
Untuk melihat semua tables dan data di cofind.db
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

def view_database():
    """View all tables and their row counts"""
    
    if not os.path.exists(DB_PATH):
        print(f"Database tidak ditemukan: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print("\n" + "="*70)
    print("DATABASE: cofind.db")
    print("="*70)
    
    if not tables:
        print("Tidak ada tables dalam database")
        conn.close()
        return
    
    print(f"\nTotal Tables: {len(tables)}\n")
    
    # Show each table with row count
    for (table_name,) in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        print(f"Table: {table_name}")
        print(f"  Rows: {count}")
        print(f"  Columns: {', '.join(column_names)}")
        print()
    
    conn.close()
    print("="*70)
    print("\nUntuk melihat data table tertentu, gunakan:")
    print("  python view_table.py <nama_table>")
    print("\nContoh:")
    print("  python view_table.py users")
    print("  python view_table.py coffee_shops")
    print("  python view_table.py reviews")
    print()

if __name__ == '__main__':
    view_database()
