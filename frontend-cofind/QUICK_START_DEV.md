# ⚡ Quick Start - Development Mode Optimization

## 🎯 Masalah yang Diperbaiki

**SEBELUM:** Setiap refresh page harus menunggu 5-10 detik untuk fetching data 😫

**SEKARANG:** Data muncul **INSTANT** (< 100ms) setelah first load! 🚀

---

## ✅ Cara Menggunakan

### 1. Start Development Server (Seperti Biasa)

```bash
cd frontend-cofind
npm run dev
```

### 2. First Load (Pertama Kali)

```
http://localhost:5173
```

- Loading akan memakan waktu 5-10 detik (normal, fetch dari API)
- Data akan di-save ke cache otomatis

### 3. Refresh Page (Subsequent Loads)

```
Tekan F5 atau Ctrl+R
```

- **Data muncul INSTANT!** ⚡
- Fresh data di-fetch di background
- Tidak perlu menunggu loading screen

---

## 🎨 UI Indicators

Saat data dari cache, akan muncul badge:

```
📦 Cached
```

Jika ingin fetch fresh data, klik:

```
🔄 Clear Cache
```

---

## 🔧 Console Commands (Optional)

Buka DevTools Console (F12):

```javascript
// Clear cache
window.__cofindDevCache.clear()

// Check cache info
window.__cofindDevCache.info()
```

---

## ⚙️ Configuration

### Adjust Cache Duration

Edit `frontend-cofind/src/utils/devCache.js`:

```javascript
// Line 5 - Default: 5 menit
const DEV_CACHE_TTL = 5 * 60 * 1000;

// Untuk cache lebih lama (10 menit):
const DEV_CACHE_TTL = 10 * 60 * 1000;

// Untuk cache lebih pendek (1 menit):
const DEV_CACHE_TTL = 1 * 60 * 1000;
```

---

## 🚨 Kapan Harus Clear Cache?

Clear cache saat:

1. ✅ **Backend code berubah** (API response structure berubah)
2. ✅ **Data tidak sesuai** (melihat data lama)
3. ✅ **Testing API changes** (ingin test endpoint baru)

**Cara Clear:**
- Klik tombol "🔄 Clear Cache" di UI
- Atau: `window.__cofindDevCache.clear()` di console

---

## 📊 Performance

### Before Optimization:
```
Refresh 1: 10 detik
Refresh 2: 10 detik
Refresh 3: 10 detik
Total: 30 detik
```

### After Optimization:
```
Refresh 1: 10 detik (first load)
Refresh 2: 0.1 detik (from cache)
Refresh 3: 0.1 detik (from cache)
Total: 10.2 detik
```

**Speed up: 90% faster!** 🚀

---

## 🎉 That's It!

Development cache bekerja **otomatis**. Tidak perlu konfigurasi apapun!

Enjoy faster development! ⚡

