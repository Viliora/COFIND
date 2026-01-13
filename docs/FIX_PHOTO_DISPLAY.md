# Cara Update Photo URLs untuk Semua Coffee Shops

Foto tidak muncul karena **kolom `places.photo_url` di database masih NULL** - belum diisi dengan URL Supabase Storage.

Sudah ada **15 foto di Supabase Storage** dalam bucket `coffee_shops`, tapi database perlu tahu URL-nya untuk menampilkan foto.

## ⚡ QUICK FIX (Recommended - SQL Direct)

### Untuk User dengan Akses SQL:
1. **Buka Supabase Dashboard** → **SQL Editor**
2. **Copy-paste query ini**:

```sql
UPDATE places
SET photo_url = 'https://storage.supabase.co/storage/v1/object/public/coffee_shops/' || place_id || '.webp'
WHERE photo_url IS NULL 
   OR photo_url NOT LIKE '%storage.supabase.co%';
```

3. **Klik tombol "RUN"** di pojok kanan
4. **Lihat notif**: "X rows updated"
5. **Refresh app** dan foto muncul! ✅

---

## Alternatif: Gunakan Admin Page

### Jika tidak bisa akses SQL:
1. **Buka app**: http://localhost:5174
2. **Login** sebagai admin
3. **Navigasi ke**: http://localhost:5174/admin/photo-update
4. **Klik "Bulk Update Photo URLs"** dan tunggu selesai

**Syarat**: Browser punya Supabase SDK yang configured dengan credentials valid

---

## Browser Console (Jika Page Error)

Jika Admin Page tidak bekerja:

1. **Buka DevTools**: `F12`
2. **Go to Console tab**
3. **Jalankan command ini**:

```javascript
await window.updatePhotoUrls()
```

Tunggu sampai selesai. Output akan menunjukkan berapa banyak yang diupdate.

---

## Setelah Update

1. **Refresh halaman**: `Ctrl + R` atau `Cmd + R`
2. **Lihat catalog** - foto sudah muncul! ✅

Jika masih tidak muncul:
- **Clear browser cache**: `Ctrl + Shift + Delete`
- **Check console** untuk error messages
- **Verify** database update berhasil (cek Supabase Studio)


