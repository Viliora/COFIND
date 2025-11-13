# 🔍 DEBUG GUIDE - Google Places API Reviews

Panduan untuk debug dan melihat raw data reviews dari Google Places API.

## 📋 Endpoint Debug

### Debug Endpoint - Lihat Raw Google Places API Response

```
GET /api/debug/coffeeshops/detail/{place_id}
```

**URL Lengkap:**
```
http://localhost:5000/api/debug/coffeeshops/detail/{place_id}
```

---

## 🚀 Cara Menggunakan

### Step 1: Dapatkan Place ID

Pertama, cari coffee shop untuk mendapatkan `place_id`:

```
http://localhost:5000/api/search/coffeeshops?location=Pontianak
```

Dari response, copy `place_id` dari salah satu coffee shop.

**Contoh Response:**
```json
{
  "status": "success",
  "data": [
    {
      "place_id": "ChIJ3V-lHxkxKi4Rq2CKtB1H2V0",
      "name": "Coffee Shop Name",
      ...
    }
  ]
}
```

### Step 2: Test Debug Endpoint

Ganti `{place_id}` dengan ID yang sudah didapat:

```
http://localhost:5000/api/debug/coffeeshops/detail/ChIJ3V-lHxkxKi4Rq2CKtB1H2V0
```

### Step 3: Analisis Response

Debug endpoint akan return:

```json
{
  "status": "success",
  "place_name": "Coffee Shop Name",
  "place_id": "ChIJ3V-lHxkxKi4Rq2CKtB1H2V0",
  "google_response_status": "OK",
  "total_reviews_from_google": 15,
  "reviews_with_text": 8,
  "message": "Google returned 15 reviews total, 8 with text content",
  "all_reviews": [...],
  "reviews_with_text_only": [...]
}
```

---

## 📊 Interpretasi Results

| Field | Arti |
|-------|------|
| `total_reviews_from_google` | Jumlah total reviews dari Google (bisa includes reviews tanpa teks) |
| `reviews_with_text` | Jumlah reviews yang punya text content |
| `all_reviews` | Array semua reviews dari Google (raw data) |
| `reviews_with_text_only` | Array reviews yang sudah difilter (hanya yang punya text) |

---

## 🔧 Testing via PowerShell

### Test 1: Get Place ID

```powershell
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/search/coffeeshops?location=Pontianak" -UseBasicParsing
$data = $response.Content | ConvertFrom-Json
$placeId = $data.data[0].place_id
Write-Host "First place_id: $placeId"
```

### Test 2: Debug Reviews

```powershell
$debugUrl = "http://localhost:5000/api/debug/coffeeshops/detail/$placeId"
$response = Invoke-WebRequest -Uri $debugUrl -UseBasicParsing
$data = $response.Content | ConvertFrom-Json

Write-Host "Place: $($data.place_name)"
Write-Host "Total Reviews: $($data.total_reviews_from_google)"
Write-Host "Reviews with Text: $($data.reviews_with_text)"
Write-Host "Message: $($data.message)"
```

### Test 3: View All Reviews Details

```powershell
$debugUrl = "http://localhost:5000/api/debug/coffeeshops/detail/$placeId"
$response = Invoke-WebRequest -Uri $debugUrl -UseBasicParsing
$data = $response.Content | ConvertFrom-Json

$data.all_reviews | ForEach-Object {
    Write-Host "---"
    Write-Host "Author: $($_.author_name)"
    Write-Host "Rating: $($_.rating)"
    Write-Host "Time: $($_.relative_time_description)"
    Write-Host "Text: $($_.text.Substring(0, 50))..."
}
```

---

## 🎯 Contoh Output Debug

### Scenario 1: Coffee Shop dengan Banyak Reviews
```json
{
  "total_reviews_from_google": 25,
  "reviews_with_text": 15,
  "message": "Google returned 25 reviews total, 15 with text content"
}
```
✅ **Interpretation:** Google ada 15 reviews yang bisa ditampilkan

### Scenario 2: Coffee Shop dengan Sedikit Reviews
```json
{
  "total_reviews_from_google": 3,
  "reviews_with_text": 2,
  "message": "Google returned 3 reviews total, 2 with text content"
}
```
⚠️ **Interpretation:** Hanya 2 reviews yang valid. Ini adalah limitasi dari Google, bukan bug kode.

### Scenario 3: Coffee Shop Baru (Belum ada reviews)
```json
{
  "total_reviews_from_google": 0,
  "reviews_with_text": 0,
  "message": "Google returned 0 reviews total, 0 with text content"
}
```
📭 **Interpretation:** Coffee shop belum ada review

---

## 📝 Struktur Data Review

Setiap review di `all_reviews` memiliki struktur:

```javascript
{
  "author_name": "Nama Pengguna",
  "author_url": "https://google.com/...",
  "language": "id",
  "profile_photo_url": "https://...",
  "rating": 4,
  "relative_time_description": "2 minggu lalu",
  "text": "Isi review lengkap...",
  "time": 1699584000
}
```

---

## 🎓 Kesimpulan

Setelah testing debug endpoint, Anda akan tahu:

1. **Berapa banyak reviews** yang sebenarnya dikirim Google untuk setiap coffee shop
2. **Apakah Google memang mengirim hanya 1-3 reviews** (limitasi API)
3. **Atau frontend yang belum di-reload** (perlu clear cache)
4. **Atau ada configuration yang salah** di backend

---

## 📌 Next Steps

Setelah debug, Anda bisa decide:

- **Option A:** Reviews yang ditampilkan sesuai dengan Google (jika Google hanya kirim 1-3)
- **Option B:** Tambah custom reviews database
- **Option C:** Upgrade ke paid Google Places API tier

Beri tahu hasil debug Anda! 👇
