#!/usr/bin/env python3
import sqlite3

DB_PATH = "c:/Users/User/cofind/cofind.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(coffee_shops)")
    cols = [c[1] for c in cur.fetchall()]
    if "map_embed_url" not in cols:
        cur.execute("ALTER TABLE coffee_shops ADD COLUMN map_embed_url TEXT")

    cur.execute("SELECT place_id FROM coffee_shops WHERE place_id IS NOT NULL AND place_id != ''")
    place_ids = [r[0] for r in cur.fetchall()]

    for pid in place_ids:
        url = f"https://www.google.com/maps?q=place_id:{pid}&output=embed"
        cur.execute(
            "UPDATE coffee_shops SET map_embed_url = ? WHERE place_id = ?",
            (url, pid),
        )

    conn.commit()
    conn.close()
    print(f"Updated map_embed_url for {len(place_ids)} rows")

if __name__ == "__main__":
    main()
