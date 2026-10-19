"""
Impor ulasan Google ke DB dari file snapshot (tanpa panggil Places API).

  python import_google_reviews_from_snapshot.py
  python import_google_reviews_from_snapshot.py --path data/google_reviews_snapshot.json

Setelah fetch manual:
  python fetch_google_places_reviews.py -o data/google_reviews_snapshot.json
  python import_google_reviews_from_snapshot.py
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from google_reviews_snapshot_import import (
    DEFAULT_SNAPSHOT_PATH,
    import_google_reviews_snapshot,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Impor ulasan Google dari snapshot JSON ke database")
    parser.add_argument(
        "--path",
        default=DEFAULT_SNAPSHOT_PATH,
        help="Path ke google_reviews_snapshot.json",
    )
    args = parser.parse_args()

    summary = import_google_reviews_snapshot(args.path)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
