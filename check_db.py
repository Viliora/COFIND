import sqlite3

conn = sqlite3.connect('cofind.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("\n📊 Tables in cofind.db:")
for table in tables:
    print(f"  ✓ {table[0]}")
    
print("\n✅ Database ready!")
conn.close()
