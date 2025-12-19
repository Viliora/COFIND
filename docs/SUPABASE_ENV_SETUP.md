# Setup Supabase Environment Variables

## 🎯 Deskripsi

File `.env` diperlukan untuk mengkonfigurasi koneksi ke Supabase. Tanpa file ini, fitur login dan database tidak akan berfungsi.

---

## 📝 Langkah Setup

### 1. **Buat File `.env`**

Buat file `.env` di folder `frontend-cofind` dengan isi:

```env
# Supabase Configuration
VITE_SUPABASE_URL=https://cpnzglvpqyugtacodwtr.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNwbnpnbHZwcXl1Z3RhY29kd3RyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU5ODM1OTUsImV4cCI6MjA4MTU1OTU5NX0.LsT5zjAWusXTvAyl8o2Qs8-FbibiSPi8qZcg0n8he68
```

### 2. **Lokasi File**

File `.env` harus berada di:
```
frontend-cofind/.env
```

**PENTING**: File `.env` sudah ada di `.gitignore`, jadi tidak akan ter-commit ke Git.

---

## 🔍 Cara Mendapatkan Supabase Credentials

### Jika Belum Punya:

1. **Buka Supabase Dashboard**: https://app.supabase.com
2. **Pilih Project** atau **Buat Project Baru**
3. **Pergi ke Settings → API**
4. **Copy**:
   - **Project URL** → `VITE_SUPABASE_URL`
   - **anon/public key** → `VITE_SUPABASE_ANON_KEY`

### Jika Sudah Punya:

Gunakan credentials yang sudah ada:
- **URL**: `https://cpnzglvpqyugtacodwtr.supabase.co`
- **Anon Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

---

## ✅ Verifikasi Setup

### 1. **Cek File `.env`**
Pastikan file ada di `frontend-cofind/.env` dengan isi yang benar.

### 2. **Restart Dev Server**
Setelah membuat/mengubah file `.env`, **restart dev server**:
```bash
# Stop server (Ctrl+C)
# Start lagi
npm run dev
```

### 3. **Cek Console**
Buka browser console, seharusnya tidak ada error:
- ❌ `No API key found in request`
- ❌ `Supabase Belum Dikonfigurasi`
- ✅ `[Auth] Supabase configured` (jika ada log ini)

### 4. **Test Login**
1. Buka halaman login
2. Seharusnya **tidak** muncul pesan "Supabase Belum Dikonfigurasi"
3. Form login seharusnya muncul

---

## 🚨 Troubleshooting

### Masalah: Masih Muncul "Supabase Belum Dikonfigurasi"

**Solusi:**
1. **Cek Lokasi File**: Pastikan `.env` ada di `frontend-cofind/.env` (bukan di root)
2. **Cek Isi File**: Pastikan tidak ada typo, tidak ada spasi di awal/akhir
3. **Restart Server**: Stop dan start lagi `npm run dev`
4. **Cek Format**: Pastikan format benar:
   ```env
   VITE_SUPABASE_URL=https://...
   VITE_SUPABASE_ANON_KEY=eyJ...
   ```

### Masalah: Error "No API key found in request"

**Solusi:**
1. **Cek `.env`**: Pastikan `VITE_SUPABASE_ANON_KEY` ada dan benar
2. **Cek Format**: Pastikan tidak ada quotes (`"` atau `'`) di sekitar value
3. **Restart Server**: Restart dev server setelah mengubah `.env`

### Masalah: File `.env` Tidak Terbaca

**Solusi:**
1. **Cek Lokasi**: File harus di `frontend-cofind/.env`
2. **Cek Nama**: Pastikan nama file tepat `.env` (bukan `.env.txt` atau lainnya)
3. **Cek Encoding**: Pastikan file menggunakan UTF-8 encoding
4. **Restart Server**: Vite perlu restart untuk membaca `.env` baru

---

## 📋 Checklist

- [ ] File `.env` dibuat di `frontend-cofind/.env`
- [ ] `VITE_SUPABASE_URL` diisi dengan URL Supabase
- [ ] `VITE_SUPABASE_ANON_KEY` diisi dengan anon key
- [ ] Dev server di-restart setelah membuat/mengubah `.env`
- [ ] Tidak ada error di console
- [ ] Form login muncul (tidak ada pesan "Supabase Belum Dikonfigurasi")

---

## 🔒 Security Notes

1. **Jangan Commit `.env`**: File sudah ada di `.gitignore`
2. **Jangan Share Anon Key**: Meskipun "anon", jangan share secara publik
3. **Gunakan Environment Variables**: Untuk production, gunakan environment variables di hosting platform

---

## 📝 Template `.env`

```env
# Supabase Configuration
# Dapatkan dari: https://app.supabase.com/project/[project-id]/settings/api

VITE_SUPABASE_URL=https://your-project-id.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key-here
```

---

## 🔗 Related Files

- `frontend-cofind/src/lib/supabase.js` - Membaca environment variables
- `frontend-cofind/src/pages/Login.jsx` - Menampilkan error jika tidak dikonfigurasi
- `frontend-cofind/.gitignore` - Memastikan `.env` tidak ter-commit
