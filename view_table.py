#!/usr/bin/env python3
"""
View specific table data from SQLite database
Usage: python view_table.py <table_name> [limit]

Examples:
  python view_table.py users
  python view_table.py reviews 10
  python view_table.py coffee_shops 5
"""
import sqlite3
import os
import sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'cofind.db')

def view_table(table_name, limit=10):
    """View data from specific table"""
    
    if not os.path.exists(DB_PATH):
        print(f"Database tidak ditemukan: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not cursor.fetchone():
        print(f"\nTable '{table_name}' tidak ditemukan!")
        print("\nGunakan: python view_database.py untuk melihat semua tables")
        conn.close()
        return
    
    # Get total rows
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = cursor.fetchone()[0]
    
    # Get table info
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    # Fetch data
    cursor.execute(f"SELECT * FROM {table_name} LIMIT {limit}")
    rows = cursor.fetchall()
    
    print("\n" + "="*100)
    print(f"TABLE: {table_name}")
    print(f"Total Rows: {total_rows} (showing {len(rows)})")
    print("="*100)
    
    if not rows:
        print("\nTidak ada data dalam table")
    else:
        # Print header
        print("\n" + " | ".join(column_names))
        print("-" * 100)
        
        # Print rows
        for row in rows:
            row_data = []
            for col in column_names:
                value = row[col]
                # Truncate long text
                if isinstance(value, str) and len(value) > 50:
                    value = value[:47] + "..."
                row_data.append(str(value) if value is not None else "NULL")
            
            print(" | ".join(row_data))
    
    print("\n" + "="*100)
    print(f"\nShowing {len(rows)} of {total_rows} rows")
    if total_rows > limit:
        print(f"Untuk melihat lebih banyak: python view_table.py {table_name} {total_rows}")
    print()
    
    conn.close()

def main():
    if len(sys.argv) < 2:
        print("\nUsage: python view_table.py <table_name> [limit]")
        print("\nExamples:")
        print("  python view_table.py users")
        print("  python view_table.py reviews 20")
        print("  python view_table.py coffee_shops")
        print("\nGunakan 'python view_database.py' untuk melihat semua tables")
        return
    
    table_name = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    view_table(table_name, limit)

if __name__ == '__main__':
    main()
