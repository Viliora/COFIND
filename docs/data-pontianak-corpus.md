# Korpus coffee shop Pontianak (penelitian)

## Ukuran target

- **50 toko** di database setelah migrasi: 15 existing + **35 baru** dari staging JSON.
- **5 review Google** per toko baru (batas Place Details API).

## Tier pemilihan (heuristik)

| Tier | Kriteria |
|------|-----------|
| `hidden_gem` | Rating ≥ 4.9, **50 ≤ review < 200** |
| `modern_specialty` | Rating ≥ 4.5, **review ≥ 50**, review < 400, nama specialty |
| `research_diverse` | Rating ≥ 4.3, **review ≥ 50**, isi kuota variasi |

Semua kandidat wajib **`total_reviews ≥ 50`** (default skrip discovery).

Dedupe: `place_id` tidak boleh sudah ada di `coffee_shops`. Maks. **2 cabang** per brand (kunci brand dari nama).

## Alur data (JSON dulu)

```bash
# 1. Discovery + enrichment (butuh GOOGLE_PLACES_API_KEY di .env)
python scripts/places/discover_pontianak_coffee.py --dry-run
python scripts/places/discover_pontianak_coffee.py --target 35 -o data/pontianak_coffee_new_staging.json

# 2. Validasi
python scripts/places/validate_pontianak_staging.py data/pontianak_coffee_new_staging.json

# 3. Migrasi DB — hanya saat Anda siap
python scripts/places/import_pontianak_staging.py --dry-run
python scripts/places/import_pontianak_staging.py
```

Artefak:

- [`data/pontianak_coffee_discovery_raw.json`](../data/pontianak_coffee_discovery_raw.json) — pool kandidat + near_miss
- [`data/pontianak_coffee_new_staging.json`](../data/pontianak_coffee_new_staging.json) — 35 toko + review untuk impor

Modul API bersama: [`places_api_client.py`](../places_api_client.py).

## Supplement (kekinian / prioritas nama)

```bash
python scripts/places/append_pontianak_supplement.py --fetch-target 35
```

- Places API **New** `searchText` + `includedType`: `cafe`, `coffee_shop`
- Query contoh: cafe kekinian / coffee shop / cafe modern Pontianak
- **Tanpa** `min_reviews`; ulasan Legacy **`reviews_sort=newest`**
- Prioritas: CW Coffee & Eatery, TOSS cafe, Weng Coffee, Lokale, tumbuh — lalu isi sisa kuota
- **Merge** ke `pontianak_coffee_new_staging.json` (entri lama tidak dihapus)

## Metodologi skripsi

Jelaskan bahwa label “modern” tidak tersedia di Places API; pemilihan memakai kombinasi text search multi-query, filter geografis Pontianak, tier di atas, dan audit field `selection_notes` / `discovery_raw`.
