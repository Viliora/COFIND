# ⚡ Quick Fix: Foto Tidak Muncul

## 🎯 Masalah

Foto coffee shop di halaman **Detail** dan **Favorite** tidak muncul (hanya placeholder warna).

---

## ✅ Solusi Cepat (3 Langkah)

### **1️⃣ Restart Backend**

**Option A: Gunakan Script (Termudah)**

Double-click file: `restart-backend.bat`

**Option B: Manual**

```bash
# Stop backend (Ctrl+C di terminal Flask)
# Lalu start lagi:
cd C:\Users\User\cofind
python app.py
```

### **2️⃣ Clear Chrome Cache**

1. Buka DevTools: `F12`
2. **Klik kanan** tombol Refresh (⟳)
3. Pilih **"Empty Cache and Hard Reload"**

### **3️⃣ Test**

1. Buka halaman Detail: `http://localhost:5173/shop/...`
2. **Foto harus muncul!** ✅

---

## 🔍 Verify Backend Sudah Benar

Saat buka halaman Detail, check log backend:

```
[DETAIL] Found 5 photos, converting to URLs...
[DETAIL] Total photos converted: 5
```

**Jika tidak ada log ini** → Backend belum di-restart!

---

## 🐛 Masih Tidak Muncul?

### **Clear Dev Cache:**

```javascript
// Di Console (F12)
window.__cofindDevCache.clear()
location.reload()
```

### **Check Network Response:**

1. DevTools (`F12`) → Tab **Network**
2. Buka halaman Detail
3. Cari request: `detail/ChIJ...`
4. Tab **Response** → Check field `photos`

**Harus array of URLs:**
```json
{
  "photos": [
    "https://maps.googleapis.com/..."
  ]
}
```

**BUKAN array of objects:**
```json
{
  "photos": [
    {"photo_reference": "..."}  // ❌ SALAH
  ]
}
```

---

## 📞 Bantuan Lebih Lanjut

Jika masih bermasalah:
1. Screenshot error di Console
2. Screenshot Network response
3. Tanyakan lagi dengan screenshot tersebut

Atau baca dokumentasi lengkap: `FIX_FOTO_TIDAK_MUNCUL.md`

