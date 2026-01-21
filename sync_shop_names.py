#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(r"c:/Users/User/cofind/cofind.db")
FACILITIES_PATH = Path(r"c:/Users/User/cofind/frontend-cofind/src/data/facilities.json")

def main():
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    if not FACILITIES_PATH.exists():
        raise SystemExit(f"Facilities file not found: {FACILITIES_PATH}")

    with FACILITIES_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    facilities = data.get("facilities_by_place_id", {})

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cur = conn.cursor()
    updated = 0
    missing = 0

    for place_id, info in facilities.items():
        name = (info or {}).get("name")
        if not name:
            continue
        cur.execute(
            "UPDATE coffee_shops SET name = ? WHERE place_id = ?",
            (name, place_id),
        )
        if cur.rowcount:
            updated += cur.rowcount
        else:
            missing += 1

    conn.commit()
    conn.close()

    print(f"Updated names: {updated}")
    print(f"Not found in coffee_shops: {missing}")

if __name__ == "__main__":
    main()
