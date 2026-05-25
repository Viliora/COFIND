# Panduan pengujian CoFind

Dokumen ini menjelaskan **cara menjalankan seluruh rangkaian tes** pada proyek CoFind (backend Flask + frontend React/Vite).

## Ringkasan jenis tes

| Lapisan | Alat | Lokasi | Apa yang diuji |
|--------|------|--------|----------------|
| Unit (backend) | **PyTest** | `tests/test_*.py` | Fungsi murni / util DB terisolasi (SQLite temp) |
| Integration (API + DB) | **PyTest** + Flask `test_client` | `tests/integration/` | Endpoint HTTP, query DB, modul `auth`, favorit, review, want-to-visit, pencarian |
| Kontrak API | **PyTest** + **jsonschema** | `tests/integration/test_api_contract.py` | Status, `Content-Type`, body, JSON Schema, auth & otorisasi admin |
| Unit (frontend) | **Vitest** | `frontend-cofind/src/**/*.test.js` | Util JS: keyword mapping, rekomendasi, recently viewed |
| End-to-end (browser) | **Playwright** | `frontend-cofind/e2e/` | Alur login, profil, favorit dari UI |
| Smoke API (opsional) | **Newman** | `tests/newman/*.json` | Hit API ke server yang **sudah jalan** |
| Performa (beban) | **Locust** (utama), **k6** (opsional) | `tests/performance/` | Load, stress, spike terhadap API yang **sudah jalan** |

---

## Prasyarat

1. **Python 3.x** dengan dependensi dev:

   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Node.js** (LTS disarankan) untuk frontend:

   ```bash
   cd frontend-cofind
   npm install
   ```

3. **Browser Playwright** (hanya jika menjalankan E2E):

   ```bash
   cd frontend-cofind
   npx playwright install chromium
   ```

---

## Menjalankan semua tes backend (unit + integration)

Dari **akar repositori** (`cofind/`):

```bash
python -m pytest tests -v
```

Ringkas (quiet):

```bash
python -m pytest tests -q
```

Hanya tes bertanda **integration** (API + DB terisolasi, tidak memakai `cofind.db` produksi):

```bash
python -m pytest -m integration -v
```

Hanya **kontrak API** (status, header JSON, validasi skema, auth/admin):

```bash
python -m pytest -m api_contract -v
```

### Integrasi penuh terhadap Postgres / Supabase

Paket `tests/integration` dapat dijalankan terhadap **database Postgres nyata** (misalnya proyek Supabase staging) dengan mengatur lingkungan berikut:

1. Terapkan skema: jalankan `schema_postgres.sql` di SQL Editor Supabase (atau `psql`) pada database target.
2. Set **connection string** Postgres (biasanya dari dashboard Supabase → Database → URI, `sslmode=require`).
3. Set backend integrasi ke Postgres dan jalankan pytest yang sama:

**Windows (PowerShell):**

```powershell
$env:COFIND_INTEGRATION_BACKEND = "postgres"
# URL dalam tanda kutip; user pooler Supabase biasanya `postgres.<project_ref>`.
$env:DATABASE_URL = "postgresql://postgres.<ref>:PASSWORD@HOST:5432/postgres?sslmode=require"
# atau: $env:SUPABASE_DB_URL = "postgresql://..."
python -m pip install -r requirements-dev.txt
python -m pytest tests/integration -m integration -v
```

**Linux / macOS:**

```bash
COFIND_INTEGRATION_BACKEND=postgres DATABASE_URL='postgresql://...' \
  python -m pytest tests/integration -m integration -v
```

**Peringatan:** setiap tes memanggil `TRUNCATE ... CASCADE` pada tabel aplikasi (`users`, `coffee_shops`, `reviews`, dll.). **Jangan** memakai database produksi yang berisi data nyata. Gunakan proyek atau schema **staging** khusus pengujian.

Hanya tes **unit** (bukan folder integration):

```bash
python -m pytest -m "not integration" -v
```

---

## Menjalankan tes unit frontend (Vitest)

Dari folder **`frontend-cofind/`**:

```bash
npm test
```

Mode watch saat mengembangkan:

```bash
npm run test:watch
```

---

## Menjalankan tes End-to-End (Playwright)

E2E memakai **port terpisah** agar tidak bentrok dengan pengembangan harian:

- Frontend tes: **5174**
- Backend tes: **5055** (SQLite, env dipaksa lewat konfigurasi Playwright)

Dari **`frontend-cofind/`**:

```bash
npm run test:e2e
```

Untuk CI (satu worker, retry):

```bash
npm run test:e2e:ci
```

UI interaktif:

```bash
npm run test:e2e:ui
```

**Catatan:** Anda boleh tetap menjalankan `python app.py` di port **5000** dan `npm run dev` di **5173**; tes E2E tidak memakai port tersebut.

---

## Newman (Postman) — opsional

Jalankan backend dulu (`python app.py` di port default Anda), lalu:

```bash
npx newman run tests/newman/cofind-api.postman_collection.json --env-var baseUrl=http://127.0.0.1:5000
```

Sesuaikan `baseUrl` jika API Anda di host/port lain.

---

## Pengujian performa (load / stress / spike)

Menguji **API yang sudah berjalan** (mis. `python app.py` di `http://127.0.0.1:5000`). Bukan menggantikan PyTest.

| Jenis | Tujuan ringkas |
|--------|----------------|
| **Load** | Trafik realistis dalam waktu lama: latensi, throughput, error rate di bawah beban stabil. |
| **Stress** | Menaikkan beban hingga di atas kapasitas normal: titik patah, pemulihan, degradasi. |
| **Spike** | Lonjakan tiba-tiba (banyak user/koneksi sekaligus): ketahanan terhadap burst. |

**Pemilihan alat (ringkas):**

| Alat | Kelebihan singkat |
|------|-------------------|
| **Locust** | Python, skrip Python, UI web; cocok dengan repo ini (`pip install`). |
| **k6** | Ringan, skrip JavaScript, bagus di CI; instal terpisah dari [k6.io](https://k6.io/docs/get-started/installation/). |
| **JMeter** | GUI + rapor; cocok tim yang sudah pakai ekosistem Java. |
| **Gatling** | Scala, laporan HTML kuat; cocok tim JVM. |

### Locust (disarankan di proyek ini)

```bash
pip install -r requirements-dev.txt
# Terminal 1: jalankan API
python app.py
# Terminal 2: mode UI
locust -f tests/performance/locustfile.py
# Buka http://localhost:8089 — set jumlah user & spawn rate sesuai skenario.

# Headless — contoh load (50 user, +10/s, 3 menit)
locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 3m --host http://127.0.0.1:5000

# Stress: naikkan -u / -t (mis. -u 200 -r 25 -t 10m)
# Spike: naikkan -r (spawn rate) tajam (mis. -u 150 -r 80 -t 2m)
```

Host lain: set `LOCUST_HOST` atau opsi `--host`.

### k6 (opsional)

Setelah `k6` terpasang:

```bash
k6 run tests/performance/k6/load.js
k6 run tests/performance/k6/spike.js
# Host lain:
k6 run -e BASE_URL=http://127.0.0.1:5055 tests/performance/k6/load.js
```

**Peringatan:** skenario baca-dominan (`/health`, `/api/coffeeshops`, pencarian). Menambah alur **signup/login** massal akan mengisi DB; lakukan hanya di **staging** atau dengan data sekali pakai.

---

## Cek cepat “satu perintah” (manual)

Urutan yang disarankan sebelum merge:

```bash
# Di akar repo
python -m pytest tests -q

# Di frontend-cofind
npm test
npm run test:e2e:ci
```

---

## Struktur berkas tes

```
cofind/
├── pytest.ini                 # konfigurasi PyTest
├── requirements-dev.txt       # pytest + requirements.txt
├── tests/
│   ├── conftest.py            # penanda @integration untuk tests/integration/
│   ├── test_favorites_utils.py
│   ├── test_review_utils_pure.py
│   ├── integration/
│   │   ├── conftest.py        # SQLite temp + fixture client Flask
│   │   ├── test_api_smoke.py
│   │   ├── test_api_auth.py
│   │   ├── test_api_coffeeshops.py
│   │   ├── test_api_search_and_detail.py
│   │   ├── test_api_favorites.py
│   │   ├── test_api_want_to_visit.py
│   │   ├── test_api_reviews.py
│   │   └── test_api_contract.py
│   ├── performance/
│   │   ├── locustfile.py      # Locust: load / stress / spike
│   │   └── k6/
│   │       ├── load.js
│   │       └── spike.js
│   └── newman/
│       └── cofind-api.postman_collection.json
└── frontend-cofind/
    ├── vitest.config.js
    ├── playwright.config.js
    ├── e2e/
    │   ├── auth.spec.js
    │   ├── user-journey.spec.js
    │   └── favorite-flow.spec.js
    └── src/utils/
        ├── *.test.js          # unit Vitest
        └── ...
```

---

## Pemecahan masalah

| Gejala | Kemungkinan penyebab |
|--------|----------------------|
| Integration PyTest gagal di mesin yang memaksa Postgres | Pastikan tidak ada konflik; tes integration memakai SQLite file sementara lewat `db_backend.DATABASE_PATH`. |
| Playwright: port sudah dipakai | Tutup proses lain di **5174** / **5055**, atau set `PW_E2E_FRONTEND_PORT` / `PW_E2E_API_PORT` di environment (lihat `playwright.config.js`). |
| E2E favorit: dilewati / gagal | Butuh data `coffee_shops` di DB SQLite yang dipakai proses Flask E2E (port 5055). |
| `playwright: command not found` | Jalankan dari `frontend-cofind` setelah `npm install`; gunakan `npx playwright test`. |
| Locust: connection refused | Pastikan Flask (atau target) sudah jalan; cek `--host` / `LOCUST_HOST`. |
| k6: command not found | Instal k6 dari dokumentasi resmi; skrip ada di `tests/performance/k6/`. |

---

## Cakupan saat ini (ringkas)

- **Backend:** util favorit & review (unit); smoke, auth, katalog, pencarian, detail by `place_id`, favorit, want-to-visit, review (integration).
- **Frontend:** util rekomendasi, keyword, recently viewed (Vitest); login, profil, favorit (Playwright).

Tambahan produksi: tes mutasi, Lighthouse, aksesibilitas, dan **pengujian beban** (`tests/performance/`, lihat bagian Locust/k6).
