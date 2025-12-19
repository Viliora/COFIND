# Perbaikan: Supabase Belum Dikonfigurasi

## 🔧 Masalah

Muncul pesan error:
> **"Supabase Belum Dikonfigurasi"**  
> Fitur login memerlukan konfigurasi Supabase. Silakan tambahkan VITE_SUPABASE_URL dan VITE_SUPABASE_ANON_KEY di file .env

Console menunjukkan:
- `No API key found in request`
- `401 (Unauthorized)` errors

---

## ✅ Solusi

### **File `.env` Sudah Ada!**

File `.env` sudah ada di `frontend-cofind/.env` dengan konfigurasi yang benar:
```env
VITE_SUPABASE_URL=https://cpnzglvpqyugtacodwtr.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### **Masalah: Dev Server Perlu Restart**

Vite hanya membaca `.env` saat **startup**. Jika file `.env` dibuat atau diubah setelah dev server berjalan, **perlu restart**.

---

## 🔄 Langkah Perbaikan

### 1. **Stop Dev Server**
Tekan `Ctrl + C` di terminal yang menjalankan `npm run dev`

### 2. **Start Ulang Dev Server**
```bash
npm run dev
```

### 3. **Refresh Browser**
Hard refresh: `Ctrl + Shift + R` atau `Ctrl + F5`

### 4. **Verifikasi**
- ✅ Tidak ada pesan "Supabase Belum Dikonfigurasi"
- ✅ Form login muncul
- ✅ Tidak ada error "No API key found" di console

---

## 🔍 Verifikasi Setup

### Cek File `.env`
Pastikan file ada di lokasi yang benar:
```
frontend-cofind/.env  ✅ (BENAR)
.env                  ❌ (SALAH - harus di folder frontend-cofind)
```

### Cek Isi File
Pastikan format benar (tidak ada quotes, tidak ada spasi):
```env
VITE_SUPABASE_URL=https://cpnzglvpqyugtacodwtr.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**SALAH:**
```env
VITE_SUPABASE_URL="https://..."  ❌ (jangan pakai quotes)
VITE_SUPABASE_URL = https://...  ❌ (jangan pakai spasi)
```

**BENAR:**
```env
VITE_SUPABASE_URL=https://...    ✅
```

---

## 🚨 Troubleshooting

### Masalah: Masih Muncul Error Setelah Restart

**Solusi 1: Cek Lokasi File**
```bash
# Pastikan file ada di folder frontend-cofind
cd frontend-cofind
ls .env  # atau dir .env di Windows
```

**Solusi 2: Cek Format File**
- Pastikan tidak ada BOM (Byte Order Mark)
- Pastikan encoding UTF-8
- Pastikan tidak ada karakter aneh

**Solusi 3: Clear Cache Vite**
```bash
# Hapus cache Vite
rm -rf node_modules/.vite  # Linux/Mac
rmdir /s node_modules\.vite  # Windows

# Restart server
npm run dev
```

**Solusi 4: Cek Console untuk Debug**
Buka browser console dan cek:
```javascript
// Di console, cek apakah env variables ter-load
console.log(import.meta.env.VITE_SUPABASE_URL)
console.log(import.meta.env.VITE_SUPABASE_ANON_KEY)
```

Jika `undefined`, berarti Vite tidak membaca `.env`.

---

## 📋 Checklist

- [x] File `.env` ada di `frontend-cofind/.env`
- [x] `VITE_SUPABASE_URL` sudah diisi
- [x] `VITE_SUPABASE_ANON_KEY` sudah diisi
- [ ] **Dev server di-restart** (PENTING!)
- [ ] Browser di-refresh (hard refresh)
- [ ] Tidak ada error di console
- [ ] Form login muncul

---

## 💡 Tips

1. **Selalu Restart**: Setiap kali mengubah `.env`, restart dev server
2. **Cek Console**: Selalu cek browser console untuk error
3. **Hard Refresh**: Gunakan `Ctrl + Shift + R` untuk clear cache browser
4. **Vite Prefix**: Pastikan variable dimulai dengan `VITE_` (Vite requirement)

---

## 🔗 Related

- `docs/SUPABASE_ENV_SETUP.md` - Setup lengkap environment variables
- `frontend-cofind/src/lib/supabase.js` - Kode yang membaca env variables
