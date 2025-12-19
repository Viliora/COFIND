# Konfigurasi Supabase Auth untuk CoFind

## ⚠️ Konfigurasi Penting yang Perlu Dicek

### 1. Email Confirmation (PENTING!)

Supabase secara default memerlukan email confirmation. Untuk development dan kemudahan user, **DISARANKAN untuk menonaktifkan email confirmation**.

**Cara menonaktifkan:**
1. Buka Supabase Dashboard
2. Pergi ke **Authentication** → **Settings** (atau **Auth** → **Settings**)
3. Cari bagian **Email Auth**
4. **Nonaktifkan** opsi **"Enable email confirmations"** atau **"Confirm email"**
5. Klik **Save**

**Mengapa?**
- User tidak perlu konfirmasi email karena kita menggunakan username (bukan email real)
- Email internal (`username@cofind.app`) tidak bisa menerima email konfirmasi
- Mempercepat proses sign up

### 2. Email Template (Opsional)

Jika email confirmation tetap aktif, pastikan template email tidak memerlukan verifikasi domain.

**Lokasi:** Authentication → Email Templates

### 3. Auth Providers

Pastikan **Email** provider aktif:
1. Buka **Authentication** → **Providers**
2. Pastikan **Email** provider **Enabled**
3. Pastikan tidak ada provider lain yang mengganggu (kecuali jika diperlukan)

### 4. Site URL & Redirect URLs

**Lokasi:** Authentication → URL Configuration

**Site URL:**
- Development: `http://localhost:5173`
- Production: `https://yourdomain.com`

**Redirect URLs:**
Tambahkan URL berikut (satu per satu, jangan gunakan wildcard `/**`):
- `http://localhost:5173` (untuk development)
- `http://localhost:5173/login` (untuk redirect setelah login)
- `http://localhost:5173/reset-password` (untuk redirect setelah reset password)
- `https://yourdomain.com` (untuk production)
- `https://yourdomain.com/login` (untuk production)

### 5. Row Level Security (RLS)

Pastikan RLS sudah di-enable dan policies sudah dibuat. Jalankan script `supabase-schema.sql` jika belum.

**Cek di:** Table Editor → pilih table → Settings → Row Level Security

### 6. Database Trigger

Pastikan trigger untuk auto-create profile sudah ada:
- Trigger: `on_auth_user_created`
- Function: `handle_new_user()`

**Cek di:** Database → Functions atau jalankan script `supabase-schema.sql`

---

## ✅ Checklist Konfigurasi

- [ ] Email confirmation **DINONAKTIFKAN**
- [ ] Email provider **ENABLED**
- [ ] Site URL sudah di-set (localhost untuk dev)
- [ ] Redirect URLs sudah ditambahkan
- [ ] RLS sudah di-enable untuk semua tables
- [ ] Policies sudah dibuat (jalankan `supabase-schema.sql`)
- [ ] Trigger `on_auth_user_created` sudah ada
- [ ] Function `handle_new_user()` sudah ada

---

## 🔧 Langkah-Langkah Setup

### Step 1: Nonaktifkan Email Confirmation

1. Login ke Supabase Dashboard
2. Pilih project Anda
3. Pergi ke **Authentication** → **Settings**
4. Scroll ke bagian **Email Auth**
5. **Toggle OFF** "Enable email confirmations"
6. Klik **Save**

### Step 2: Verifikasi Email Provider

1. Pergi ke **Authentication** → **Providers**
2. Pastikan **Email** provider **Enabled**
3. Jika tidak, klik **Enable**

### Step 3: Set Site URL

1. Pergi ke **Authentication** → **URL Configuration**
2. Set **Site URL**:
   - Development: `http://localhost:5173`
   - Production: `https://yourdomain.com`
3. Tambahkan **Redirect URLs** (tambahkan satu per satu, klik "+ Add URL" untuk setiap URL):
   - `http://localhost:5173` (untuk development)
   - `http://localhost:5173/login` (untuk redirect setelah login)
   - `http://localhost:5173/reset-password` (untuk redirect setelah reset password)
   
   **Catatan Penting:**
   - Jangan gunakan wildcard `/**` - Supabase tidak menerimanya
   - Tambahkan setiap URL secara terpisah
   - Klik "+ Add URL" untuk menambahkan URL baru
   - Setelah semua URL ditambahkan, klik "Save URLs"

### Step 4: Setup Database Schema

1. Buka **SQL Editor**
2. Copy seluruh isi file `supabase-schema.sql`
3. Paste dan jalankan di SQL Editor
4. Pastikan tidak ada error

### Step 5: Test Sign Up

1. Buka aplikasi di `http://localhost:5173`
2. Pergi ke `/login`
3. Klik "Daftar sekarang"
4. Isi form:
   - Username: `testuser`
   - Password: `test123`
5. Klik "Sign up now"
6. Seharusnya langsung berhasil tanpa perlu konfirmasi email

---

## 🐛 Troubleshooting

### Error: "Email address is invalid"

**Penyebab:** Domain email tidak valid atau email confirmation masih aktif

**Solusi:**
1. Pastikan kode sudah menggunakan `@cofind.app` (bukan `@cofind.local`)
2. Nonaktifkan email confirmation di Supabase Settings
3. Clear cache browser dan coba lagi

### Error: "User already registered"

**Penyebab:** Username sudah digunakan

**Solusi:**
- Gunakan username lain
- Atau hapus user lama di Supabase Dashboard → Authentication → Users

### Error: "Invalid login credentials"

**Penyebab:** 
- Username/password salah
- User belum terdaftar
- Email confirmation masih aktif

**Solusi:**
1. Pastikan user sudah terdaftar
2. Nonaktifkan email confirmation
3. Pastikan username dan password benar

### Error: "Failed to load resource: 403"

**Penyebab:** RLS policies tidak mengizinkan akses

**Solusi:**
1. Pastikan RLS sudah di-enable
2. Jalankan script `supabase-schema.sql` untuk membuat policies
3. Pastikan user sudah login

### Sign up berhasil tapi profile tidak terbuat

**Penyebab:** Trigger atau function tidak ada

**Solusi:**
1. Jalankan script `supabase-schema.sql`
2. Atau buat manual:
   - Function: `handle_new_user()`
   - Trigger: `on_auth_user_created`

---

## 📝 Catatan Penting

1. **Email Confirmation HARUS dinonaktifkan** karena kita menggunakan email internal (`@cofind.app`) yang tidak bisa menerima email.

2. **Domain `.app` adalah valid** dan akan diterima oleh Supabase, berbeda dengan `.local` yang ditolak.

3. **User tidak perlu tahu tentang email internal** - mereka hanya perlu memasukkan username.

4. **Untuk production**, pertimbangkan untuk:
   - Mengaktifkan email confirmation jika ingin verifikasi user
   - Atau tetap nonaktifkan untuk kemudahan user
   - Tambahkan rate limiting untuk mencegah abuse

---

## 🔐 Keamanan

Meskipun email confirmation dinonaktifkan, keamanan tetap terjaga karena:
- Password tetap diperlukan
- RLS policies melindungi data
- Username harus unique
- Password harus minimal 6 karakter (default Supabase)
