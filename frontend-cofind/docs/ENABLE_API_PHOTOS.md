# 🖼️ Cara Mengaktifkan Foto dari API

## ⚠️ MASALAH: Foto Tidak Muncul (Hanya SVG Placeholder)

### Penyebab:
Frontend masih menggunakan `places.json` (data statis tanpa foto) karena `USE_API` belum diaktifkan.

---

## ✅ SOLUSI: Aktifkan API

### **Langkah 1: Buat File `.env.local`**

Buat file baru di folder `frontend-cofind` dengan nama `.env.local`:

```bash
# Location: frontend-cofind/.env.local

# Enable API untuk mendapatkan foto dari Google Places API
VITE_USE_API=true
VITE_API_BASE=http://localhost:5000
```

### **Langkah 2: Restart Vite Dev Server**

```bash
# Stop server (Ctrl + C)
# Lalu jalankan lagi:
npm run dev
```

---

## 🔍 Verifikasi

### **1. Cek Console Browser**

Setelah restart, buka browser console (F12), Anda harus melihat:

```
[ShopList] Loading from API (network)
```

**BUKAN:**
```
[ShopList] Loading from places.json (fallback)
```

### **2. Cek Network Tab**

- Buka DevTools → Network tab
- Refresh page
- Cari request ke: `http://localhost:5000/api/search/coffeeshops`
- Status harus: `200 OK`
- Response harus berisi `photos` array dengan URL

### **3. Cek Gambar**

- Scroll halaman
- Gambar coffee shop harus muncul (bukan SVG placeholder)
- Gambar dimuat secara lazy (bertahap saat scroll)

---

## 📊 Test API Langsung

Untuk memastikan API mengembalikan foto:

```bash
# Jalankan test script
python test_api_photos.py
```

**Expected Output:**
```
Status: success
Total shops: 60
Shops WITH photos: 60
Shops WITHOUT photos: 0
Sample photo URL: https://lh3.googleusercontent.com/...
```

---

## 🐛 Troubleshooting

### **Masalah 1: Foto Masih Tidak Muncul**

**Cek:**
1. ✅ File `.env.local` sudah dibuat?
2. ✅ Vite dev server sudah di-restart?
3. ✅ Backend Flask sudah running di port 5000?
4. ✅ Browser console tidak ada error CORS?

**Solusi:**
```bash
# Terminal 1 - Backend
cd cofind
python app.py

# Terminal 2 - Frontend (restart)
cd frontend-cofind
npm run dev
```

---

### **Masalah 2: CORS Error**

Jika muncul error CORS di console:

```
Access to fetch at 'http://localhost:5000/...' from origin 'http://localhost:5173' has been blocked by CORS policy
```

**Cek `app.py`:**
```python
# Line 90 - Pastikan CORS enabled
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

---

### **Masalah 3: API Tidak Mengembalikan Data**

**Cek Google Places API Key:**

1. Buka `cofind/.env`
2. Pastikan `GOOGLE_PLACES_API_KEY` valid
3. Cek quota di [Google Cloud Console](https://console.cloud.google.com/)

---

## 📁 Struktur File yang Benar

```
frontend-cofind/
├── .env.local          ← BUAT FILE INI!
│   └── VITE_USE_API=true
│   └── VITE_API_BASE=http://localhost:5000
├── src/
│   ├── pages/
│   │   └── ShopList.jsx
│   └── components/
│       ├── OptimizedImage.jsx
│       └── CoffeeShopCard.jsx
└── ...
```

---

## 🎯 Expected Behavior Setelah Fix

### **Before (Sekarang):**
```
┌─────────────────┐
│                 │
│   [SVG Only]    │
│       ☕        │
│                 │
└─────────────────┘
```

### **After (Setelah Enable API):**
```
┌─────────────────┐
│                 │
│ [Real Photo]    │
│  Coffee Shop    │
│                 │
└─────────────────┘
```

---

## 🚀 Quick Fix (Copy-Paste)

**Buat file `.env.local` di `frontend-cofind/`:**

```env
VITE_USE_API=true
VITE_API_BASE=http://localhost:5000
```

**Restart Vite:**

```bash
# Ctrl + C untuk stop
npm run dev
```

**Refresh browser** → Foto harus muncul! 🎉

---

## ✅ Checklist

- [ ] Backend Flask running (port 5000)
- [ ] File `.env.local` sudah dibuat
- [ ] `VITE_USE_API=true` di `.env.local`
- [ ] Vite dev server sudah di-restart
- [ ] Browser sudah di-refresh
- [ ] Console menunjukkan "Loading from API"
- [ ] Foto coffee shop muncul (bukan SVG)

---

**Status API:** ✅ API sudah mengembalikan foto (60/60 shops)  
**Status Frontend:** ⚠️ Perlu enable `USE_API=true`

---

**Setelah fix, foto akan dimuat dengan:**
- ⚡ Lazy loading
- 🎨 Progressive loading
- 🛡️ Smart fallback
- 💫 Smooth transitions

Semua optimasi sudah siap! Tinggal aktifkan API! 🚀

