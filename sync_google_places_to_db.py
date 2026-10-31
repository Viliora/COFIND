"""
Impor facilities.json (jika ada) lalu sync metadata Google Places ke coffee_shops.

Untuk ulasan Google, sumber operasional di DB: impor snapshot
(`import_google_reviews_from_snapshot.py`), bukan sync rutin ini.

  python sync_google_places_to_db.py
  python sync_google_places_to_db.py --skip-json-import
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from google_places_sync import sync_all_shops


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--skip-json-import',
        action='store_true',
        help='Lewati impor awal dari facilities.json',
    )
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument(
        '--from-staging',
        type=str,
        default='',
        help='Path JSON staging; sync hanya place_id di shops[]',
    )
    parser.add_argument(
        '--use-text-search',
        action='store_true',
        help='Resolve place via text search (default: place_id langsung)',
    )
    args = parser.parse_args()

    if args.from_staging:
        import json
        from pathlib import Path

        from google_places_sync import sync_shops_by_place_ids

        payload = json.loads(Path(args.from_staging).read_text(encoding='utf-8'))
        ids = [
            str(s.get('place_id') or '')
            for s in (payload.get('shops') or [])
            if s.get('place_id')
        ]
        summary = sync_shops_by_place_ids(
            ids,
            use_text_search=args.use_text_search,
        )
    else:
        summary = sync_all_shops(
            limit=args.limit,
            import_json_first=not args.skip_json_import,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get('error_count', 0) < summary.get('shop_count', 1) else 1


if __name__ == '__main__':
    raise SystemExit(main())
