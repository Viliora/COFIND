# Perbaikan: Error "failed to parse filter" saat Submit Review

## 🔧 Masalah yang Diperbaiki

### ❌ **Masalah:**
Saat submit review, muncul error:
> **"Gagal menyimpan review: 'failed to parse filter (1766136939115)' (line 1, column 1)"**

Console menunjukkan:
- `400 (Bad Request)` untuk semua request ke Supabase
- Error code: `PGRST100`
- Details: `unexpected "1" expecting "not" or operator (eq, gt, ...)`

### ✅ **Penyebab:**
Query parameter cache-busting (`_t=timestamp`) yang ditambahkan di custom fetch function **diinterpretasikan sebagai filter** oleh Supabase PostgREST API. PostgREST memproses semua query parameters sebagai filter, sehingga `_t=1766136939115` dianggap sebagai filter yang tidak valid.

---

## 🔄 Perbaikan yang Dibuat

### 1. **Supabase Client - Hapus Query Parameter Cache-Busting (`supabase.js`)**

**Sebelum (SALAH):**
```javascript
// Add cache-busting query parameter to URL
const urlObj = new URL(url);
urlObj.searchParams.set('_t', Date.now().toString()); // ❌ Ini menyebabkan error!

return fetch(urlObj.toString(), noCacheOptions);
```

**Sesudah (BENAR):**
```javascript
// CRITICAL: Jangan tambahkan query parameter cache-busting di URL Supabase
// PostgREST akan menginterpretasikan semua query params sebagai filter
// Gunakan hanya headers untuk cache-busting, bukan query parameter

// JANGAN modifikasi URL - biarkan Supabase client handle query params dengan benar
return fetch(url, noCacheOptions);
```

### 2. **Service Worker - Skip Query Parameter untuk Supabase (`sw.js`)**

**Sebelum (SALAH):**
```javascript
// Add cache-busting query parameter to URL
const url = new URL(request.url);
url.searchParams.set('_sw_t', Date.now().toString()); // ❌ Juga menyebabkan error untuk Supabase!
```

**Sesudah (BENAR):**
```javascript
// Check if this is a Supabase request
const url = new URL(request.url);
const isSupabaseRequest = url.hostname.includes('supabase.co');

// Only add cache-busting query param for non-Supabase requests
if (!isSupabaseRequest) {
  url.searchParams.set('_sw_t', Date.now().toString());
}

// Use original URL for Supabase, modified URL for others
const cacheBustingRequest = new Request(
  isSupabaseRequest ? request.url : url.toString(),
  ...
);
```

### 3. **ReviewList - Hapus Abort Signal (`ReviewList.jsx`)**

**Sebelum:**
```javascript
.order('created_at', { ascending: false })
.abortSignal(new AbortController().signal); // Tidak perlu, bisa menyebabkan issue
```

**Sesudah:**
```javascript
.order('created_at', { ascending: false }); // Clean dan simple
```

---

## ✅ Hasil Setelah Perbaikan

### Sebelum:
- ❌ Error "failed to parse filter" saat submit review
- ❌ 400 Bad Request untuk semua request ke Supabase
- ❌ Review tidak bisa di-submit
- ❌ Review tidak bisa di-fetch

### Sesudah:
- ✅ Review berhasil di-submit
- ✅ Tidak ada error "failed to parse filter"
- ✅ Request ke Supabase berhasil (status 200/201)
- ✅ Review tampil dengan benar

---

## 🔍 Root Cause Analysis

### Masalah Utama: PostgREST Query Parameter Parsing

Supabase menggunakan **PostgREST** yang memproses semua query parameters sebagai:
1. **Filter operators** (`eq`, `gt`, `lt`, `in`, dll)
2. **Select columns**
3. **Order by**
4. **Pagination**

Ketika kita menambahkan query parameter arbitrary seperti `_t=1766136939115`, PostgREST mencoba memparsingnya sebagai filter dan gagal karena formatnya tidak valid.

### Solusi:
1. **Jangan tambahkan query parameter** untuk Supabase requests
2. **Gunakan hanya headers** untuk cache-busting
3. **Biarkan Supabase client** handle query params dengan benar

---

## 🧪 Testing

### Test Case 1: Submit Review
1. Login sebagai user
2. Buka detail coffee shop
3. Isi form review (rating + text + foto)
4. Klik "Kirim Review"
5. **Expected**: 
   - Review berhasil di-submit
   - Tidak ada error "failed to parse filter"
   - Review muncul di list

### Test Case 2: Fetch Reviews
1. Buka detail coffee shop
2. **Expected**: 
   - Review tampil dengan benar
   - Tidak ada error 400
   - Tidak ada error "failed to parse filter"

### Test Case 3: Cek Network Tab
1. Buka Network tab di DevTools
2. Submit review atau refresh halaman
3. **Expected**:
   - Request ke Supabase berhasil (status 200/201)
   - URL tidak memiliki query parameter `_t` atau `_sw_t`
   - Headers memiliki `Cache-Control: no-cache`

---

## 📊 Monitoring

### Console Logs untuk Debugging:
- `[Supabase] Fetching (NO CACHE): [url]` - URL tidak memiliki `_t` parameter ✅
- **TIDAK ada** error "failed to parse filter" ✅
- **TIDAK ada** error 400 Bad Request ✅
- Request ke Supabase berhasil (status 200/201) ✅

### Network Tab:
- Request URL **TIDAK** memiliki query parameter `_t` atau `_sw_t` untuk Supabase
- Status response harus 200/201 (bukan 400)
- Headers request harus ada `Cache-Control: no-cache, no-store`

---

## 🔧 Troubleshooting

### Masalah: Masih Error "failed to parse filter"

**Solusi:**
1. **Cek URL**: Di Network tab, pastikan URL tidak memiliki `_t=` atau `_sw_t=`
2. **Hard Refresh**: `Ctrl + Shift + R` untuk clear cache
3. **Restart Dev Server**: Restart setelah perubahan kode
4. **Cek Console**: Lihat log `[Supabase] Fetching` untuk verifikasi URL

### Masalah: Review Masih Tidak Bisa Submit

**Solusi:**
1. **Cek Error**: Lihat error message di console
2. **Cek Network Tab**: Lihat request POST ke `/rest/v1/reviews`
3. **Cek RLS Policy**: Pastikan policy untuk INSERT reviews aktif
4. **Cek User ID**: Pastikan user authenticated dan `user.id` ada

---

## ✅ Checklist

- [x] Hapus query parameter `_t` dari Supabase requests
- [x] Service Worker skip query parameter untuk Supabase
- [x] Gunakan hanya headers untuk cache-busting
- [x] Review berhasil di-submit
- [x] Tidak ada error "failed to parse filter"
- [x] Request ke Supabase berhasil

---

## 📝 Catatan Penting

1. **PostgREST Behavior**: PostgREST memproses semua query params sebagai filter/select/order
2. **No Arbitrary Params**: Jangan tambahkan query parameter arbitrary untuk Supabase
3. **Headers Only**: Gunakan hanya headers untuk cache-busting (Cache-Control, Pragma, dll)
4. **Supabase Client**: Biarkan Supabase client handle query params dengan benar

---

## 🔗 Related Files

- `frontend-cofind/src/lib/supabase.js` - Custom fetch function (fixed)
- `frontend-cofind/public/sw.js` - Service Worker network strategy (fixed)
- `frontend-cofind/src/components/ReviewList.jsx` - Review fetching (cleaned)
- `frontend-cofind/src/components/ReviewForm.jsx` - Review submission
