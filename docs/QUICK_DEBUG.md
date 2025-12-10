# 🚀 QUICK START - Debug Reviews

## Step 1: Pastikan Backend Jalan
```powershell
cd C:\Users\User\cofind
python app.py
```
Backend akan berjalan di `http://localhost:5000`

## Step 2: Cari Place ID Coffee Shop

Buka PowerShell baru dan jalankan:

```powershell
$response = Invoke-WebRequest -Uri "http://localhost:5000/api/search/coffeeshops?location=Pontianak" -UseBasicParsing
$data = $response.Content | ConvertFrom-Json
$placeId = $data.data[0].place_id
Write-Host "Place ID: $placeId"
```

## Step 3: Debug Reviews dari Google

Ganti `{PLACE_ID}` dengan hasil dari Step 2:

**Via Browser:**
```
http://localhost:5000/api/debug/coffeeshops/detail/{PLACE_ID}
```

**Atau Via PowerShell:**
```powershell
$debugUrl = "http://localhost:5000/api/debug/coffeeshops/detail/$placeId"
$response = Invoke-WebRequest -Uri $debugUrl -UseBasicParsing
$data = $response.Content | ConvertFrom-Json

Write-Host "Coffee Shop: $($data.place_name)"
Write-Host "Total Reviews: $($data.total_reviews_from_google)"
Write-Host "Reviews with Text: $($data.reviews_with_text)"
Write-Host ""
Write-Host $data.message
```

## Step 4: Lihat Detail Semua Reviews

```powershell
$data.all_reviews | ForEach-Object {
    Write-Host ""
    Write-Host "👤 $($_.author_name) - Rating: $($_.rating)⭐"
    Write-Host "📅 $($_.relative_time_description)"
    Write-Host "💬 $($_.text)"
}
```

## Interpretasi

- **Total Reviews > 3** = Google memang kirim banyak reviews
- **Total Reviews ≤ 3** = Ini adalah limitasi Google Places API free tier
- **Reviews with Text < Total Reviews** = Ada reviews tanpa teks

---

📌 Hasil dari debug ini akan membantu kita decide apakah perlu:
- Upgrade ke paid API tier
- Tambah custom reviews database
- Atau terima limitasi Google

**Silakan jalankan debug dan share hasilnya!** 👇
