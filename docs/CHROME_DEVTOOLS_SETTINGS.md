# Pengaturan Chrome DevTools untuk Debugging Cache

## ✅ Pengaturan yang Sudah Benar

### 1. **"Nonaktifkan cache" (Disable cache)**
- ✅ **Status**: Sudah dicentang (benar)
- ✅ **Fungsi**: Mencegah browser cache response saat DevTools terbuka
- ✅ **Untuk**: Memastikan data Supabase selalu fresh saat debugging

---

## ⚠️ Pengaturan yang Perlu Diubah

### 2. **"Pertahankan log" (Preserve log)**
- ❌ **Status**: Saat ini tidak dicentang (dimatikan)
- ✅ **Rekomendasi**: **CENTANG** (aktifkan)
- ✅ **Alasan**: 
  - Log akan tetap ada setelah refresh halaman
  - Membantu melihat request sebelum dan sesudah refresh
  - Penting untuk debugging masalah cache yang terjadi setelah refresh
  - Bisa melihat apakah request ke Supabase benar-benar dibuat setiap refresh

---

## ⚙️ Pengaturan Tambahan di Settings (Gear Icon)

Klik ikon **roda gigi (⚙️)** di pojok kanan atas tab Network untuk membuka pengaturan lanjutan:

### ✅ **Pengaturan yang WAJIB diaktifkan:**

#### 1. **Record network log**
- ✅ **Centang** (biasanya sudah aktif default)
- **Fungsi**: Merekam semua request jaringan

#### 2. **Disable cache (while DevTools is open)**
- ✅ **Centang** (sama dengan "Nonaktifkan cache" di toolbar)
- **Fungsi**: Memastikan cache benar-benar dinonaktifkan

#### 3. **Show overview**
- ✅ **Centang** (opsional, tapi berguna)
- **Fungsi**: Menampilkan timeline grafik request

### 🔍 **Pengaturan untuk Debugging Lanjutan:**

#### 4. **Capture screenshots**
- ⚪ **Opsional** (centang jika perlu)
- **Fungsi**: Mengambil screenshot saat halaman dimuat
- **Kapan digunakan**: Untuk melihat visual state saat request terjadi

#### 5. **Show request blocking**
- ⚪ **Opsional** (untuk testing)
- **Fungsi**: Memblokir request tertentu untuk testing

---

## 🎯 Rekomendasi Pengaturan Lengkap

### **Toolbar Network Tab:**
```
✅ Nonaktifkan cache        [X] (CENTANG)
✅ Pertahankan log          [X] (CENTANG - UBAH INI!)
   Throttling              [Tanpa throttling] (OK)
```

### **Settings (Gear Icon):**
```
✅ Record network log                    [X]
✅ Disable cache (while DevTools open)   [X]
✅ Show overview                         [X]
⚪ Capture screenshots                   [ ]
⚪ Show request blocking                 [ ]
```

---

## 📋 Checklist Pengaturan

### Sebelum Debugging:
- [x] ✅ "Nonaktifkan cache" dicentang
- [ ] ⚠️ **"Pertahankan log" dicentang** (UBAH INI!)
- [x] ✅ Settings → "Disable cache" dicentang
- [x] ✅ Settings → "Record network log" dicentang

### Saat Debugging Review:
1. ✅ Buka DevTools → Network tab
2. ✅ Centang "Nonaktifkan cache"
3. ✅ **Centang "Pertahankan log"** (penting!)
4. ✅ Buka detail coffee shop
5. ✅ Lihat request ke Supabase (harus status 200, bukan 304)
6. ✅ Refresh halaman (log tetap ada karena "Pertahankan log" aktif)
7. ✅ Cek apakah request baru dibuat atau menggunakan cache

---

## 🔍 Cara Verifikasi Pengaturan Benar

### Test 1: Verifikasi "Pertahankan log"
1. Buka Network tab
2. **Centang** "Pertahankan log"
3. Buka detail coffee shop
4. Lihat request ke Supabase muncul di log
5. Refresh halaman (F5)
6. **Expected**: Request baru muncul di log (tidak hilang)
7. **Jika log hilang**: "Pertahankan log" belum aktif

### Test 2: Verifikasi "Nonaktifkan cache"
1. Buka Network tab
2. **Centang** "Nonaktifkan cache"
3. Buka detail coffee shop
4. Lihat request ke Supabase
5. **Cek Status**: Harus **200** (bukan 304)
6. **Cek Size**: Harus menunjukkan ukuran file (bukan "disk cache" atau "memory cache")
7. **Cek Time**: Harus menunjukkan waktu request (bukan 0ms)

### Test 3: Verifikasi Request Fresh
1. Buka Network tab dengan semua pengaturan aktif
2. Buka detail coffee shop
3. Lihat request ke Supabase: `https://cpnzglvpqyugtacodwtr.supabase.co/rest/v1/reviews?...`
4. **Cek Headers Request**:
   - `Cache-Control: no-cache, no-store, must-revalidate` ✅
   - `Pragma: no-cache` ✅
   - `X-Request-Time: [timestamp]` ✅
5. **Cek Response Headers**:
   - Status: `200 OK` (bukan `304 Not Modified`)
   - `Cache-Control: no-cache, no-store` ✅

---

## 🚨 Troubleshooting

### Masalah: Request Masih Status 304
**Solusi:**
1. Pastikan "Nonaktifkan cache" dicentang
2. Pastikan Settings → "Disable cache" dicentang
3. Hard refresh: `Ctrl + Shift + R`
4. Clear Service Worker di Application tab

### Masalah: Log Hilang Setelah Refresh
**Solusi:**
1. Centang "Pertahankan log"
2. Refresh halaman
3. Log seharusnya tetap ada

### Masalah: Tidak Melihat Request ke Supabase
**Solusi:**
1. Pastikan "Record network log" aktif di Settings
2. Filter: Ketik "supabase" di filter box
3. Pastikan tidak ada filter lain yang aktif

---

## 📊 Monitoring Request Supabase

### Yang Harus Terlihat di Network Tab:

#### Request URL:
```
https://cpnzglvpqyugtacodwtr.supabase.co/rest/v1/reviews?place_id=eq.ChIJ...
```

#### Request Headers:
```
Cache-Control: no-cache, no-store, must-revalidate
Pragma: no-cache
Expires: 0
X-Request-Time: 1234567890
```

#### Response:
```
Status: 200 OK (bukan 304!)
Size: [ukuran file] (bukan "disk cache")
Time: [waktu request] (bukan 0ms)
```

#### Response Headers:
```
Cache-Control: no-cache, no-store, must-revalidate
Content-Type: application/json
```

---

## ✅ Kesimpulan

### Pengaturan yang Benar:
1. ✅ **"Nonaktifkan cache"**: Sudah benar (dicentang)
2. ⚠️ **"Pertahankan log"**: **UBAH - CENTANG** (penting untuk debugging)
3. ✅ **Settings → "Disable cache"**: Centang
4. ✅ **Settings → "Record network log"**: Centang

### Setelah Mengubah Pengaturan:
1. Hard refresh: `Ctrl + Shift + R`
2. Test buka detail coffee shop
3. Cek Network tab untuk request Supabase
4. Pastikan status 200 (bukan 304)
5. Refresh lagi, pastikan log tetap ada

---

## 📝 Catatan Penting

- **"Nonaktifkan cache"** hanya bekerja saat DevTools terbuka
- **"Pertahankan log"** penting untuk melihat request sebelum dan sesudah refresh
- Pengaturan ini hanya untuk debugging, tidak mempengaruhi production
- Untuk production, kode sudah diatur untuk no-cache (lihat `FIX_REVIEW_CACHE_ISSUE.md`)
