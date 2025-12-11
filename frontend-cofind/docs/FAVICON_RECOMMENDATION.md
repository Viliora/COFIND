# Rekomendasi: vite.svg vs Logo Project

## Status Saat Ini

`vite.svg` saat ini digunakan sebagai:
1. **Favicon** di `index.html` (line 5)
2. **PWA Icon** di `manifest.json` (line 12, 26, 33)
3. **Service Worker Notification Icon** di `sw.js` (line 469, 470)

## Lokasi File

### ✅ **Tetap di `public/` (REKOMENDASI)**
- File di `public/` bisa diakses langsung via URL path (`/vite.svg`)
- Cocok untuk favicon dan PWA icon yang perlu diakses via URL
- Tidak perlu di-import di kode

### ❌ **Tidak cocok di `assets/`**
- File di `assets/` perlu di-import di kode JavaScript
- Favicon dan PWA icon harus bisa diakses via URL path langsung
- Browser dan PWA system tidak bisa import dari assets

## Opsi untuk Logo Project

### Opsi 1: Ganti vite.svg dengan Logo Project (REKOMENDASI)
Jika ingin menggunakan logo project sendiri:

1. **Copy `cofind.svg` ke `public/` sebagai favicon:**
   ```bash
   cp src/assets/cofind.svg public/cofind-favicon.svg
   ```

2. **Update `index.html`:**
   ```html
   <link rel="icon" type="image/svg+xml" href="/cofind-favicon.svg" />
   ```

3. **Update `manifest.json`:**
   ```json
   "icons": [
     {
       "src": "/cofind-favicon.svg",
       "sizes": "any",
       "type": "image/svg+xml"
     }
   ]
   ```

4. **Update `sw.js`:**
   ```javascript
   icon: '/cofind-favicon.svg',
   badge: '/cofind-favicon.svg',
   ```

5. **Hapus `vite.svg`** (opsional)

### Opsi 2: Buat Favicon Khusus
Buat favicon khusus untuk project (16x16, 32x32, atau SVG) dan letakkan di `public/`.

### Opsi 3: Tetap Gunakan vite.svg
Jika tidak masalah dengan branding Vite, bisa tetap menggunakan `vite.svg`.

## Kesimpulan

**REKOMENDASI:**
- ✅ **Tetap di `public/`** - Lokasi yang benar untuk favicon dan PWA icon
- ✅ **Ganti dengan logo project** - Untuk branding yang konsisten
- ❌ **Jangan pindah ke `assets/`** - Tidak akan berfungsi sebagai favicon/PWA icon


