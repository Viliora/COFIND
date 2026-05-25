"""List nama dan alamat coffee shop dari database (Supabase/PostgreSQL atau SQLite lokal)."""
from db_backend import get_connection, dict_from_row

conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT name, address FROM coffee_shops ORDER BY name")
rows = [dict_from_row(cur, r) for r in cur.fetchall()]
conn.close()

for i, r in enumerate(rows, 1):
    name = (r.get("name") if r else None) or "-"
    address = (r.get("address") if r else None) or "-"
    print(f"{i}. {name}")
    print(f"   Alamat: {address}")
    print()

print(f"Total: {len(rows)} coffee shop")
