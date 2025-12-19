# Checklist Setup CoFind - Login & Admin System

## ✅ Yang Sudah Selesai

- [x] Database schema sudah dibuat (tables, RLS, policies, triggers)
- [x] Field `role` sudah ditambahkan ke table `profiles`
- [x] Script SQL berhasil dijalankan tanpa error

---

## 📋 Langkah Selanjutnya

### 1. ✅ Verifikasi Konfigurasi Supabase Auth

**Lokasi:** Supabase Dashboard → Authentication → Settings

- [ ] **Email Confirmation DINONAKTIFKAN** (PENTING!)
  - Pergi ke Authentication → Settings
  - Scroll ke bagian "Email Auth"
  - Toggle OFF "Enable email confirmations"
  - Klik Save

- [ ] **Email Provider Enabled**
  - Pergi ke Authentication → Providers
  - Pastikan "Email" provider Enabled

- [ ] **Site URL & Redirect URLs**
  - Pergi ke Authentication → URL Configuration
  - Set Site URL: `http://localhost:5173` (untuk development)
  - Tambahkan Redirect URLs (satu per satu):
    - `http://localhost:5173`
    - `http://localhost:5173/login`
    - `http://localhost:5173/reset-password`
  - Klik "Save URLs"

---

### 2. ✅ Test Sign Up & Login

1. **Buka aplikasi:**
   - Pastikan frontend berjalan di `http://localhost:5173`
   - Jika belum, jalankan: `npm run dev` di folder `frontend-cofind`

2. **Test Sign Up:**
   - Buka `/login`
   - Klik "Daftar sekarang"
   - Isi form:
     - Username: `testuser`
     - Password: `test123` (minimal 6 karakter)
   - Klik "Sign up now"
   - **Seharusnya langsung berhasil** (tanpa perlu konfirmasi email)

3. **Test Login:**
   - Logout (jika sudah login)
   - Login dengan username: `testuser` dan password: `test123`
   - **Seharusnya langsung masuk**

4. **Verifikasi:**
   - Cek di Navbar → dropdown user → seharusnya ada "Profil Saya"
   - Cek di Supabase Dashboard → Authentication → Users → seharusnya ada user baru

---

### 3. ✅ Buat User Admin

**Langkah 1: Daftar User Admin**
- Buka `/login`
- Klik "Daftar sekarang"
- Buat akun dengan:
  - Username: `admin`
  - Password: `admin123` (atau password kuat lainnya)
- Login dengan akun tersebut

**Langkah 2: Set Role Admin di Supabase**
1. Buka Supabase Dashboard → SQL Editor
2. Jalankan query ini:

```sql
-- Set user sebagai admin
UPDATE profiles 
SET role = 'admin' 
WHERE username = 'admin';
```

3. Verifikasi:

```sql
-- Cek apakah sudah admin
SELECT username, role FROM profiles WHERE username = 'admin';
```

**Langkah 3: Test Admin Access**
1. Logout dari aplikasi
2. Login kembali dengan username: `admin`
3. Cek di Navbar → dropdown user → seharusnya ada link **"Admin Panel"**
4. Klik "Admin Panel" atau akses langsung `/admin`
5. Seharusnya bisa masuk ke halaman admin dashboard

---

### 4. ✅ Test Fitur User

**Test Review:**
- [ ] Buka detail coffee shop (`/shop/{place_id}`)
- [ ] Scroll ke bagian review
- [ ] Klik "Tulis Review" (hanya muncul jika sudah login)
- [ ] Isi form review dengan rating, teks, dan foto (opsional)
- [ ] Submit review
- [ ] Verifikasi review muncul di halaman

**Test Favorite:**
- [ ] Buka detail coffee shop
- [ ] Klik tombol favorite (hati) di pojok kanan bawah
- [ ] Buka halaman `/favorite`
- [ ] Verifikasi coffee shop muncul di list favorite

**Test Want to Visit:**
- [ ] Buka detail coffee shop
- [ ] Klik tombol "Want to Visit" (bookmark) di pojok kanan bawah
- [ ] Buka halaman `/want-to-visit`
- [ ] Verifikasi coffee shop muncul di list

**Test Guest Access:**
- [ ] Logout dari aplikasi
- [ ] Buka detail coffee shop
- [ ] **Verifikasi:** Tombol favorite dan want to visit **TIDAK muncul**
- [ ] **Verifikasi:** Form review **TIDAK muncul**
- [ ] Buka `/favorite` → seharusnya muncul prompt login
- [ ] Buka `/want-to-visit` → seharusnya muncul prompt login

---

### 5. ✅ Test Admin Features

**Test Admin Dashboard:**
- [ ] Login sebagai admin
- [ ] Akses `/admin`
- [ ] Verifikasi dashboard menampilkan:
  - Total Users
  - Total Reviews
  - Total Reports
  - Pending Reports
- [ ] Verifikasi "Recent Reviews" menampilkan 10 review terbaru
- [ ] Verifikasi "Recent Reports" menampilkan 10 report terbaru

**Test Admin Actions:**
- [ ] Jika ada pending reports, test tombol "Approve" dan "Dismiss"
- [ ] Verifikasi status report berubah setelah action

---

## 🐛 Troubleshooting

### Sign Up Gagal dengan Error "Email address is invalid"

**Solusi:**
1. Pastikan email confirmation sudah dinonaktifkan
2. Pastikan kode menggunakan `@cofind.app` (bukan `@cofind.local`)
3. Clear cache browser dan coba lagi

### Login Gagal dengan Error "Invalid login credentials"

**Solusi:**
1. Pastikan user sudah terdaftar
2. Pastikan email confirmation sudah dinonaktifkan
3. Pastikan username dan password benar
4. Cek di Supabase Dashboard → Authentication → Users apakah user ada

### Admin Panel Tidak Muncul di Navbar

**Solusi:**
1. Pastikan user sudah di-set sebagai admin:
   ```sql
   SELECT username, role FROM profiles WHERE username = 'admin';
   ```
2. Logout dan login kembali (untuk refresh `isAdmin` state)
3. Cek console browser untuk error

### Profile Tidak Terbuat Setelah Sign Up

**Solusi:**
1. Pastikan trigger `on_auth_user_created` sudah ada
2. Pastikan function `handle_new_user()` sudah ada
3. Cek di Supabase Dashboard → Database → Functions
4. Jika tidak ada, jalankan script `supabase-schema-safe.sql` lagi

---

## ✅ Final Checklist

Setelah semua langkah di atas selesai, pastikan:

- [ ] Sign up berhasil tanpa error
- [ ] Login berhasil tanpa error
- [ ] User bisa membuat review
- [ ] User bisa menambah favorite dan want to visit
- [ ] Guest tidak bisa akses fitur yang memerlukan login
- [ ] Admin bisa akses `/admin`
- [ ] Admin dashboard menampilkan data dengan benar
- [ ] Admin bisa manage reports

---

## 🎉 Selesai!

Jika semua checklist sudah selesai, sistem login dan admin sudah siap digunakan!

**Catatan:**
- Untuk production, jangan lupa update Site URL dan Redirect URLs ke domain production
- Pertimbangkan untuk mengaktifkan email confirmation jika diperlukan
- Gunakan password yang kuat untuk akun admin
