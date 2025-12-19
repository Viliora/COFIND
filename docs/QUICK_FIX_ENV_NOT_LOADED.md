# Quick Fix: Environment Variables Tidak Ter-Load

## 🔧 Masalah

Muncul pesan "Supabase Belum Dikonfigurasi" meskipun file `.env` sudah ada dan benar.

## ✅ Solusi Cepat

### **Langkah 1: Restart Dev Server**

Vite hanya membaca `.env` saat **startup**. Jika file dibuat atau diubah setelah dev server berjalan, **perlu restart**.

1. **Stop Dev Server**: Tekan `Ctrl + C` di terminal
2. **Start Ulang**: 
   ```bash
   npm run dev
   ```
3. **Hard Refresh Browser**: `Ctrl + Shift + R`

### **Langkah 2: Verifikasi di Console**

Setelah restart, buka browser console. Seharusnya muncul log:
```
[Supabase Config] ✅ Supabase dikonfigurasi dengan benar
```

Jika masih muncul:
```
[Supabase Config] ⚠️ Supabase tidak dikonfigurasi!
```

Maka ada masalah dengan file `.env`.

---

## 🔍 Verifikasi File `.env`

### 1. **Cek Lokasi File**
File harus ada di:
```
frontend-cofind/.env  ✅ (BENAR)
.env                  ❌ (SALAH)
```

### 2. **Cek Isi File**
Buka file `.env` dan pastikan format benar:
```env
VITE_SUPABASE_URL=https://cpnzglvpqyugtacodwtr.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**PENTING:**
- ❌ Jangan pakai quotes: `VITE_SUPABASE_URL="https://..."`
- ❌ Jangan pakai spasi: `VITE_SUPABASE_URL = https://...`
- ✅ Format benar: `VITE_SUPABASE_URL=https://...`

### 3. **Cek Console untuk Debug**
Setelah restart, cek console untuk log:
```
[Supabase Config] Environment variables check: {
  hasUrl: true,
  hasKey: true,
  ...
}
```

---

## 🚨 Troubleshooting

### Masalah: Masih "Supabase Belum Dikonfigurasi" Setelah Restart

**Solusi 1: Cek Lokasi File**
```bash
# Di terminal, pastikan file ada
cd frontend-cofind
dir .env  # Windows
ls .env   # Linux/Mac
```

**Solusi 2: Cek Format File**
- Pastikan tidak ada BOM (Byte Order Mark)
- Pastikan encoding UTF-8
- Pastikan tidak ada karakter aneh di akhir file

**Solusi 3: Clear Cache Vite**
```bash
# Hapus cache Vite
rmdir /s node_modules\.vite  # Windows
rm -rf node_modules/.vite    # Linux/Mac

# Restart server
npm run dev
```

**Solusi 4: Cek di Browser Console**
Buka console dan ketik:
```javascript
console.log(import.meta.env.VITE_SUPABASE_URL)
console.log(import.meta.env.VITE_SUPABASE_ANON_KEY)
```

Jika `undefined`, berarti Vite tidak membaca `.env`.

---

## 📋 Checklist

- [ ] File `.env` ada di `frontend-cofind/.env`
- [ ] Format file benar (tidak ada quotes, tidak ada spasi)
- [ ] **Dev server di-restart** (PENTING!)
- [ ] Browser di-refresh (hard refresh: `Ctrl + Shift + R`)
- [ ] Console menunjukkan `[Supabase Config] ✅ Supabase dikonfigurasi`
- [ ] Tidak ada pesan "Supabase Belum Dikonfigurasi"

---

## 💡 Tips

1. **Selalu Restart**: Setiap kali mengubah `.env`, restart dev server
2. **Cek Console**: Selalu cek browser console untuk log `[Supabase Config]`
3. **Hard Refresh**: Gunakan `Ctrl + Shift + R` untuk clear cache browser
4. **Vite Prefix**: Pastikan variable dimulai dengan `VITE_` (Vite requirement)

---

## 🔗 Related

- `docs/FIX_SUPABASE_NOT_CONFIGURED.md` - Troubleshooting lengkap
- `docs/SUPABASE_ENV_SETUP.md` - Setup environment variables
