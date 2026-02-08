"""List nama dan alamat coffee shop dari database."""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'cofind.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT name, address FROM coffee_shops ORDER BY name')
rows = cur.fetchall()
conn.close()

for i, r in enumerate(rows, 1):
    name = r['name'] or '-'
    address = r['address'] or '-'
    print(f"{i}. {name}")
    print(f"   Alamat: {address}")
    print()

print(f"Total: {len(rows)} coffee shop")
