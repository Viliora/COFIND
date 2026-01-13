# FIX: Supabase Storage Photo URL - ERR_NAME_NOT_RESOLVED Error

## Problem (Masalah)

**Error pada Console:**
```
Failed to load resource: net::ERR_NAME_NOT_RESOLVED
storage.supabase.co/...
```

### Penyebab Error:
1. **Format URL salah** - Photo URL di tabel `places` tidak memiliki format yang benar
2. **Path tidak valid** - URL menggunakan struktur path yang tidak sesuai dengan Supabase Storage
3. **Domain salah** - Domain atau struktur bucket tidak sesuai dengan konfigurasi

### Format URL yang BENAR:
```
https://storage.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp
```

**Breakdown:**
- Domain: `storage.supabase.co`
- Path: `/storage/v1/object/public/coffee_shops/`
- Filename: `{place_id}.webp` (contoh: `ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp`)

---

## Solution (Solusi)

### **Option 1: Auto-Fix dari Browser Console (RECOMMENDED - FASTEST)**

1. **Buka aplikasi** di browser: `http://localhost:5174` (atau port Vite)
2. **Buka Developer Tools** (F12 → Console)
3. **Copy-paste salah satu perintah berikut:**

#### Quick Fix - Fix semua URLs sekaligus:
```javascript
// Diagnose dulu - lihat berapa banyak URL yang bermasalah
await window.diagnosticPhotoUrl.diagnosePhotoUrls();

// Baru fix semuanya
await window.fixPhotoUrl.fixAllPhotoUrls();
```

#### Alternative - Bulk fix (lebih cepat):
```javascript
await window.fixPhotoUrl.fixAllPhotoUrlsBulk();
```

**Contoh Output:**
```
🔍 [DIAGNOSTIC] Starting photo URL diagnosis...
   ✅ Valid format: 15/60
   ❌ Invalid format: 40/60
   ⚠️  Missing URL: 5/60

🔧 [FIX] Starting to fix all photo URLs...
   ✅ Fixed: 45/60
   ⏭️  Skipped: 15/60
```

4. **Refresh browser** (Ctrl + F5)
5. **Foto sekarang muncul** ✅

---

### **Option 2: SQL Direct - Supabase Dashboard (FASTEST IF YOU HAVE SQL ACCESS)**

1. **Buka Supabase Dashboard** → SQL Editor
2. **Copy-paste query ini:**

```sql
-- Update all places dengan format URL yang benar
UPDATE places
SET photo_url = 'https://storage.supabase.co/storage/v1/object/public/coffee_shops/' || place_id || '.webp'
WHERE photo_url IS NULL 
   OR photo_url NOT LIKE '%storage.supabase.co%'
   OR photo_url NOT LIKE '%/storage/v1/object/public/coffee_shops/%';
```

3. **Klik RUN** (tombol pojok kanan)
4. **Lihat notif**: "X rows updated"
5. **Refresh app** dan foto muncul ✅

---

### **Option 3: Python Script - Backend Update**

Jika ingin update dari backend:

```bash
cd c:\Users\User\cofind
python .\update_photo_urls.py
```

---

## Verification (Verifikasi)

Untuk memastikan semua URLs sudah benar:

```javascript
// Di browser console:
await window.diagnosticPhotoUrl.diagnosePhotoUrls();
```

Output yang diharapkan:
```
✅ Valid format: 60/60
❌ Invalid format: 0/60
⚠️  Missing URL: 0/60
Health: 100%
```

---

## Technical Details (Untuk Developer)

### New Files Added:
1. **`src/utils/diagnosticPhotoUrl.js`** - Diagnostic tool
   - `diagnosePhotoUrls()` - Check semua URLs
   - `verifyPhotoUrlFormat(url)` - Verify single URL
   - `generateCorrectPhotoUrl(placeId)` - Generate correct URL

2. **`src/utils/fixPhotoUrl.js`** - Fix tool
   - `fixAllPhotoUrls()` - Fix semua URLs (one by one)
   - `fixAllPhotoUrlsBulk()` - Fix bulk (faster)
   - `fixSinglePhotoUrl(placeId, currentUrl)` - Fix single URL

### Modified Files:
- **`src/App.jsx`** - Auto-load diagnostic dan fix tools on app start

### URL Format Requirements:
```
✅ VALID:
https://storage.supabase.co/storage/v1/object/public/coffee_shops/ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp
https://storage.supabase.co/storage/v1/object/public/coffee_shops/{place_id}.webp

❌ INVALID:
https://storage.supabase.co/coffee_shops/ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp (missing /storage/v1/object/public/)
https://storage.supabase.co/storage/v1/object/public/ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp (wrong bucket path)
https://supabase.co/.../photo.jpg (wrong domain)
```

---

## Troubleshooting (Jika masih error)

### Error: "Supabase not configured"
- Pastikan `.env` memiliki `VITE_SUPABASE_URL` dan `VITE_SUPABASE_ANON_KEY`
- Lihat [setup guide](./FIX_SUPABASE_NOT_CONFIGURED.md)

### Error: "Permission denied"
- Pastikan RLS (Row Level Security) di tabel `places` mengizinkan UPDATE
- Check Supabase Dashboard → Authentication → Policies

### Photos masih tidak muncul setelah fix
- Clear browser cache (Ctrl + Shift + Delete)
- Pastikan bucket `coffee_shops` ada di Supabase Storage
- Check network tab di DevTools → pastikan response 200 OK

### Cara check network request:
1. F12 → Network tab
2. Refresh halaman
3. Filter dengan "storage.supabase"
4. Lihat Status code (harus 200, bukan 404/403/500)

---

## Prevention (Untuk di masa depan)

Supaya tidak terjadi lagi:

### Saat upload foto baru:
```javascript
// ✅ BENAR - Gunakan helper function
import { uploadAndUpdateCoffeeShopPhoto } from '../utils/supabasePhotoUpload';
await uploadAndUpdateCoffeeShopPhoto(placeId, imageFile);
```

### Jangan hardcode URL:
```javascript
// ❌ SALAH
coffee_shop.photo_url = 'https://.../.webp';

// ✅ BENAR
coffee_shop.photo_url = generateCorrectPhotoUrl(place_id);
```

### Testing new URLs:
```javascript
// Validate sebelum insert
import { verifyPhotoUrlFormat } from '../utils/diagnosticPhotoUrl';
const check = verifyPhotoUrlFormat(url);
if (!check.isValid) {
  throw new Error(`URL format error: ${check.issue}`);
}
```

---

## Performance Impact

- **Diagnostic scan**: ~1-2 seconds untuk 60 coffee shops
- **Fix operation**: ~1-3 seconds (tergantung network)
- **No downtime**: Can run anytime, doesn't block users

---

## Questions?

1. Cek console untuk error messages
2. Buka Supabase Dashboard untuk verify data
3. Cek `.env` untuk Supabase credentials
