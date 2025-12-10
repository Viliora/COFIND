# 📄 Penjelasan Pagination Google Places API

## ❓ Pertanyaan: Apakah Backend Memanggil 3 Halaman dengan URL Berbeda?

**JAWABAN: TIDAK!** Backend memanggil **URL yang SAMA** untuk semua halaman, yang berubah hanya **parameter `pagetoken`**.

---

## 🔄 Cara Kerja Pagination

### 1. Request Halaman Pertama (Page 1)

```http
GET https://maps.googleapis.com/maps/api/place/nearbysearch/json
```

**Parameters:**
```json
{
  "location": "-0.026330,109.342506",
  "radius": "5000",
  "type": "cafe",
  "keyword": "coffee",
  "key": "YOUR_API_KEY"
}
```

**Response:**
```json
{
  "status": "OK",
  "results": [
    { "name": "Coffee Shop 1", "place_id": "..." },
    { "name": "Coffee Shop 2", "place_id": "..." },
    ...
    { "name": "Coffee Shop 20", "place_id": "..." }
  ],
  "next_page_token": "ABC123XYZ..."  ← Token untuk halaman 2
}
```

### 2. Request Halaman Kedua (Page 2)

⏱️ **WAJIB DELAY 2 DETIK** sebelum request berikutnya!

```http
GET https://maps.googleapis.com/maps/api/place/nearbysearch/json  ← URL SAMA!
```

**Parameters:**
```json
{
  "location": "-0.026330,109.342506",
  "radius": "5000",
  "type": "cafe",
  "keyword": "coffee",
  "key": "YOUR_API_KEY",
  "pagetoken": "ABC123XYZ..."  ← TAMBAHAN INI!
}
```

**Response:**
```json
{
  "status": "OK",
  "results": [
    { "name": "Coffee Shop 21", "place_id": "..." },
    { "name": "Coffee Shop 22", "place_id": "..." },
    ...
    { "name": "Coffee Shop 40", "place_id": "..." }
  ],
  "next_page_token": "DEF456UVW..."  ← Token untuk halaman 3
}
```

### 3. Request Halaman Ketiga (Page 3)

⏱️ **WAJIB DELAY 2 DETIK** lagi!

```http
GET https://maps.googleapis.com/maps/api/place/nearbysearch/json  ← URL MASIH SAMA!
```

**Parameters:**
```json
{
  "location": "-0.026330,109.342506",
  "radius": "5000",
  "type": "cafe",
  "keyword": "coffee",
  "key": "YOUR_API_KEY",
  "pagetoken": "DEF456UVW..."  ← Token halaman 3
}
```

**Response:**
```json
{
  "status": "OK",
  "results": [
    { "name": "Coffee Shop 41", "place_id": "..." },
    { "name": "Coffee Shop 42", "place_id": "..." },
    ...
    { "name": "Coffee Shop 60", "place_id": "..." }
  ],
  "next_page_token": null  ← Tidak ada lagi halaman berikutnya
}
```

---

## 💻 Implementasi di Backend (app.py)

```python
coffee_shops = []  # Array untuk menampung semua coffee shops
page_number = 1

while True:
    # Request ke Google Places API
    response = requests.get(base_url, params=params)
    data = response.json()
    
    if data.get('status') == 'OK':
        results = data.get('results', [])
        
        # Tambahkan hasil ke array
        for place in results:
            coffee_shops.append({
                'place_id': place.get('place_id'),
                'name': place.get('name'),
                # ... data lainnya
            })
        
        # Cek apakah ada halaman berikutnya
        next_page_token = data.get('next_page_token')
        if next_page_token:
            time.sleep(2)  # WAJIB DELAY 2 DETIK!
            params['pagetoken'] = next_page_token  # Tambahkan token
            page_number += 1
        else:
            break  # Tidak ada lagi halaman berikutnya
```

---

## 🧪 Cara Testing & Debugging

### 1. Lihat Log di Terminal Backend

Sekarang backend sudah ditambahkan logging detail. Jalankan:

```bash
python app.py
```

Kemudian akses endpoint dari browser/frontend. Anda akan melihat log seperti:

```
[PAGE 1] Making request to Google Places API: https://...
[PAGE 1] Params: {'location': '-0.026330,109.342506', ...}
[PAGE 1] Response status: OK, error_message: None
[PAGE 1] Found 20 coffee shops
[PAGE 1] Next page token found: ABC123XYZ...
[PAGE 1] Total coffee shops so far: 20

[PAGE 2] Making request to Google Places API: https://...
[PAGE 2] Params: {'location': '-0.026330,109.342506', 'pagetoken': 'ABC123XYZ...'}
[PAGE 2] Response status: OK, error_message: None
[PAGE 2] Found 20 coffee shops
[PAGE 2] Next page token found: DEF456UVW...
[PAGE 2] Total coffee shops so far: 40

[PAGE 3] Making request to Google Places API: https://...
[PAGE 3] Params: {'location': '-0.026330,109.342506', 'pagetoken': 'DEF456UVW...'}
[PAGE 3] Response status: OK, error_message: None
[PAGE 3] Found 20 coffee shops
[PAGE 3] No more pages. Total coffee shops: 60
```

### 2. Gunakan Debug Endpoint

Saya sudah menambahkan endpoint khusus untuk debugging pagination:

```bash
# Akses dari browser atau curl
curl http://localhost:5000/api/debug/pagination

# Atau dengan koordinat custom
curl "http://localhost:5000/api/debug/pagination?lat=-0.026330&lng=109.342506"
```

**Response:**
```json
{
  "status": "success",
  "total_pages": 3,
  "total_shops": 60,
  "pages": [
    {
      "page_number": 1,
      "status": "OK",
      "results_count": 20,
      "has_next_page": true,
      "next_page_token": "ABC123XYZ...",
      "shop_names": [
        "Coffee Shop 1",
        "Coffee Shop 2",
        ...
      ]
    },
    {
      "page_number": 2,
      "status": "OK",
      "results_count": 20,
      "has_next_page": true,
      "next_page_token": "DEF456UVW...",
      "shop_names": [...]
    },
    {
      "page_number": 3,
      "status": "OK",
      "results_count": 20,
      "has_next_page": false,
      "next_page_token": null,
      "shop_names": [...]
    }
  ]
}
```

### 3. Test dari Frontend

Buka browser console (F12) dan lihat network tab:
1. Buka halaman shop list
2. Lihat network request ke `/api/search/coffeeshops`
3. Lihat response - akan ada 60 coffee shops (dari 3 halaman)

---

## ⚠️ Penting: Kenapa Data Bisa Berubah-ubah?

Meskipun URL dan koordinat sama, **data bisa berbeda** karena:

### 1. **Google's Ranking Algorithm**
- Google mengubah ranking berdasarkan:
  - Popularitas terkini
  - Rating dan reviews baru
  - Waktu (buka/tutup)
  - Jarak dari pusat koordinat

### 2. **Business Updates**
- Coffee shop baru dibuka
- Coffee shop lama tutup
- Perubahan informasi (rating, alamat, dll)

### 3. **API Quota & Rate Limiting**
- Jika quota habis, bisa return hasil berbeda
- Rate limiting bisa mempengaruhi pagination

### 4. **Time of Day**
- Hasil bisa berbeda pagi vs malam
- Status buka/tutup mempengaruhi ranking

---

## 🎯 Solusi: Konsistensi Data

Jika Anda ingin data yang **konsisten**:

### Opsi 1: Simpan Snapshot (Recommended untuk Testing)
```python
@app.route('/api/snapshot/save', methods=['POST'])
def save_snapshot():
    # Fetch data dari API
    # Simpan ke database/file JSON
    # Return saved data
    pass

@app.route('/api/snapshot/load', methods=['GET'])
def load_snapshot():
    # Load data dari database/file JSON
    # Return saved data
    pass
```

### Opsi 2: Server-side Caching dengan TTL
```python
# Cache data selama 5-10 menit
CACHE_TTL = 300  # 5 menit
```

### Opsi 3: Gunakan Data Lokal (places.json)
```javascript
// Di frontend
import placesData from './data/places.json';
```

---

## 📊 Limits Google Places API

- **Maksimal 20 hasil per halaman**
- **Maksimal 60 hasil total** (3 halaman)
- **Wajib delay 2 detik** antara pagination requests
- **Quota:** Tergantung plan Google Cloud Anda

---

## 🔗 Endpoint yang Tersedia

| Endpoint | Deskripsi |
|----------|-----------|
| `/api/search/coffeeshops` | Main endpoint (dengan pagination) |
| `/api/debug/pagination` | Debug pagination (lihat semua halaman) |
| `/api/debug/reviews-context` | Debug review context untuk LLM |
| `/api/test` | Test server status |

---

## ✅ Kesimpulan

1. ✅ **URL SAMA** untuk semua halaman
2. ✅ Yang berubah hanya **parameter `pagetoken`**
3. ✅ Backend otomatis fetch hingga **3 halaman (60 shops)**
4. ✅ Data bisa **berubah-ubah** karena Google's algorithm
5. ✅ Gunakan **debug endpoint** untuk melihat detail pagination

---

**Dibuat:** November 21, 2025  
**Update:** Setelah menghapus caching system

