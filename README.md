COFIND - Run & config
=====================

Ringkasan singkat
- Backend: Flask app di `app.py` (server-side yang memanggil Google Places API)
- Frontend: Vite + React di folder `frontend-cofind`

Konfigurasi API key (penting — jangan commit API key ke repo)
1. Salin `.env.example` ke `.env` di root project:

   # PowerShell
   cp .env.example .env

2. Edit `.env` dan isi `GOOGLE_PLACES_API_KEY` dengan API key Anda (contoh: AIza...)

Atau, untuk sekali jalan tanpa file, set environment variable di PowerShell dengan perintah berikut:

```powershell
Set-Item -Path Env:GOOGLE_PLACES_API_KEY -Value 'YOUR_GOOGLE_PLACES_API_KEY'
# lalu jalankan python app.py
```

Menjalankan backend (development)
---------------------------------
1. Aktifkan virtualenv (jika ada):

```powershell
& .\venv\Scripts\Activate.ps1
```

2. (Opsional) install requirements:

```powershell
pip install -r requirements.txt
```

3. Jalankan server:

```powershell
# Dari root project
python .\app.py
```

Server akan berjalan default di http://127.0.0.1:5000

Menjalankan frontend (development)
----------------------------------
1. Buka terminal baru dan masuk ke folder frontend:

```powershell
cd .\frontend-cofind
```

2. Install dependency bila belum:

```powershell
npm install
```

3. Jalankan dev server Vite:

```powershell
npm run dev
```

Frontend default: http://localhost:5173 (atau port yang diberikan oleh Vite). Frontend akan memanggil backend menggunakan `VITE_API_URL` dari `frontend-cofind/.env`.

Testing endpoints
-----------------
- Root backend: http://localhost:5000/  => returns {"message":"Welcome to COFIND API"}
- Search coffeeshops (Text Search):
  - http://localhost:5000/api/search/coffeeshops?location=Pontianak
  - or by coords: http://localhost:5000/api/search/coffeeshops?lat=0.02633&lng=109.34250

Debug & common issues
---------------------
- REQUEST_DENIED: biasanya karena API key belum enable untuk Places Web Service, billing tidak aktif, atau key dibatasi. Periksa Google Cloud Console:
  - APIs & Services -> Library -> enable "Places API" / "Places API (Web Service)"
  - Billing -> aktifkan billing pada project
  - Credentials -> API keys -> cek restrictions (untuk server-side, gunakan IP restriction atau none)

Important note about API key restrictions
---------------------------------------
- If you call Google Places from your backend (server-side requests), you must use an API key that is allowed for server-side use. Keys that have "HTTP referrer" (website) restrictions will be rejected with the message: "API keys with referer restrictions cannot be used with this API." To avoid that:
  1. Create two API keys in Google Cloud Console:
     - A browser key restricted by HTTP referrers for Maps JavaScript usage in the frontend (if you use Maps JS).
     - A server key for backend calls (Places Web Service). For testing you can leave restrictions off, but for production restrict by server IP addresses (Credentials → API key → Application restrictions → IP addresses).
  2. Put the server key in your backend `.env` as `GOOGLE_PLACES_API_KEY`.
  3. Restart your Flask server so it picks up the new `.env`.

Example (PowerShell) to set server key temporarily:
```powershell
Set-Item -Path Env:GOOGLE_PLACES_API_KEY -Value 'YOUR_SERVER_SIDE_KEY'
python .\app.py
```

If you still get REQUEST_DENIED after switching keys, check the exact `error_message` returned in the JSON response — it usually explains whether it's a restrictions issue, billing, or a disabled API.

- CORS: backend sudah mengaktifkan CORS pada `/api/*`, jadi front-end boleh mem-fetch dari port lain.

Keamanan
--------
- Jangan commit `.env` yang berisi API key ke Git. Gunakan `.env.example` sebagai template.
- Untuk production, batasi API key pada IP server (Credentials -> API key -> Application restrictions).

Jika mau, saya bisa:
- menambahkan endpoint `/api/photo?ref=...` untuk proxy foto, atau
- membuat example React component dan wiring router di `frontend-cofind/src`.
