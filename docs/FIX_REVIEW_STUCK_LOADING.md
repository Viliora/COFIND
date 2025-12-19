# Perbaikan: Review Stuck di Loading (No API Key)

## 🔧 Masalah yang Diperbaiki

### ❌ **Masalah:**
Saat user mengirim review, web stuck di loading ("Mengirim...") dan review tidak masuk ke database. Console menunjukkan error:
- `No API key found in request`
- `401 (Unauthorized)` untuk semua request ke Supabase

### ✅ **Penyebab:**
Custom `fetch` function di Supabase client **menghapus headers penting** (termasuk `apikey` dan `Authorization`) saat menambahkan cache-busting headers. Ini menyebabkan semua request ke Supabase gagal dengan 401.

---

## 🔄 Perbaikan yang Dibuat

### **supabase.js - Custom Fetch Function**

**Sebelum (SALAH):**
```javascript
headers: {
  ...options.headers,  // ❌ Tidak bekerja jika Headers object
  'Cache-Control': 'no-cache',
  ...
}
```

**Sesudah (BENAR):**
```javascript
// Convert Headers object to plain object if needed
let existingHeaders = {};
if (options.headers) {
  if (options.headers instanceof Headers) {
    // Convert Headers object to plain object
    options.headers.forEach((value, key) => {
      existingHeaders[key] = value;
    });
  } else if (typeof options.headers === 'object') {
    // Already a plain object
    existingHeaders = { ...options.headers };
  }
}

// Merge headers: preserve existing + add cache headers
const mergedHeaders = {
  ...existingHeaders, // ✅ Preserve Supabase headers (apikey, Authorization, etc.)
  'Cache-Control': 'no-cache, no-store, must-revalidate',
  'Pragma': 'no-cache',
  'Expires': '0'
};
```

---

## ✅ Hasil Setelah Perbaikan

### Sebelum:
- ❌ Review stuck di loading
- ❌ Error "No API key found in request"
- ❌ 401 Unauthorized untuk semua request
- ❌ Review tidak masuk ke database

### Sesudah:
- ✅ Review berhasil dikirim
- ✅ API key terkirim dengan benar
- ✅ Tidak ada error 401
- ✅ Review masuk ke database dan tampil di list

---

## 🔍 Root Cause Analysis

### Masalah Utama: Headers Object vs Plain Object

Supabase client mengirim headers sebagai `Headers` object (bukan plain object). Saat kita menggunakan spread operator (`...options.headers`), Headers object tidak di-spread dengan benar, sehingga headers penting seperti `apikey` hilang.

### Solusi:
1. **Deteksi tipe headers**: Cek apakah `Headers` object atau plain object
2. **Konversi jika perlu**: Convert `Headers` object ke plain object
3. **Preserve semua headers**: Pastikan semua headers asli (terutama `apikey` dan `Authorization`) tetap ada
4. **Merge dengan cache headers**: Tambahkan cache-busting headers tanpa menghapus yang lama

---

## 🧪 Testing

### Test Case 1: Submit Review
1. Login sebagai user
2. Buka detail coffee shop
3. Isi form review (rating + text)
4. Klik "Kirim Review"
5. **Expected**: 
   - Review berhasil dikirim
   - Tidak stuck di loading
   - Review muncul di list "Review Pengunjung"
   - Tidak ada error di console

### Test Case 2: Submit Review dengan Foto
1. Login sebagai user
2. Buka detail coffee shop
3. Isi form review + upload foto
4. Klik "Kirim Review"
5. **Expected**:
   - Review berhasil dikirim
   - Foto ter-upload
   - Review muncul dengan foto

### Test Case 3: Cek Console
1. Buka browser console
2. Submit review
3. **Expected**:
   - ✅ Tidak ada error "No API key found"
   - ✅ Tidak ada error 401
   - ✅ Request ke Supabase berhasil (status 200/201)

---

## 📊 Monitoring

### Console Logs untuk Debugging:
- `[Supabase] Fetching (NO CACHE):` - Setiap request Supabase
- **TIDAK ada** error "No API key found in request" ✅
- **TIDAK ada** error 401 Unauthorized ✅
- Request ke `/rest/v1/reviews` berhasil (status 200/201) ✅

### Network Tab:
- Request ke Supabase harus memiliki header `apikey`
- Request harus memiliki header `Authorization` (jika user authenticated)
- Status response harus 200/201 (bukan 401)

---

## 🔧 Troubleshooting

### Masalah: Masih Stuck di Loading

**Solusi:**
1. **Cek Console**: Lihat apakah masih ada error "No API key found"
2. **Cek Network Tab**: Lihat request ke Supabase, cek apakah header `apikey` ada
3. **Restart Dev Server**: Restart setelah perubahan kode
4. **Hard Refresh**: `Ctrl + Shift + R` untuk clear cache browser

### Masalah: Masih Error 401

**Solusi:**
1. **Cek `.env`**: Pastikan `VITE_SUPABASE_ANON_KEY` ada dan benar
2. **Cek Headers**: Di Network tab, cek apakah header `apikey` terkirim
3. **Cek Supabase Client**: Pastikan `isSupabaseConfigured` adalah `true`
4. **Cek Console**: Lihat log `[Supabase] Fetching` untuk debug

### Masalah: Review Masih Tidak Masuk

**Solusi:**
1. **Cek Database**: Cek di Supabase Dashboard apakah review masuk
2. **Cek RLS Policy**: Pastikan policy untuk INSERT reviews aktif
3. **Cek Console**: Lihat error message dari Supabase
4. **Cek User ID**: Pastikan user authenticated dan `user.id` ada

---

## ✅ Checklist

- [x] Custom fetch function preserve headers dengan benar
- [x] Headers object dikonversi ke plain object
- [x] API key terkirim di semua request
- [x] Review berhasil di-submit
- [x] Tidak ada error 401
- [x] Review muncul di list setelah submit

---

## 📝 Catatan Penting

1. **Headers Object**: Supabase menggunakan `Headers` object, bukan plain object
2. **Spread Operator**: `...headers` tidak bekerja dengan `Headers` object
3. **Preserve Headers**: Selalu preserve headers asli sebelum menambahkan yang baru
4. **API Key**: Header `apikey` **WAJIB** ada di setiap request ke Supabase

---

## 🔗 Related Files

- `frontend-cofind/src/lib/supabase.js` - Custom fetch function
- `frontend-cofind/src/components/ReviewForm.jsx` - Submit review logic
- `frontend-cofind/src/components/ReviewList.jsx` - Display reviews
