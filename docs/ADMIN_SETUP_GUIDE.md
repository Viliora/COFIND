# Panduan Setup Admin CoFind

## Cara Mengakses Admin Page

Admin page dapat diakses melalui:
- **URL**: `http://localhost:5173/admin` (development) atau `https://yourdomain.com/admin` (production)
- **Akses**: Hanya user dengan role `admin` yang dapat mengakses
- **Login**: Gunakan username dan password yang sudah di-set sebagai admin

## Cara Membuat User Admin

### Metode 1: Membuat User Baru Lalu Set Sebagai Admin (Recommended)

1. **Daftar User Baru**:
   - Buka halaman `/login`
   - Klik "Daftar sekarang"
   - Buat akun dengan username dan password (contoh: `admin`, `admin123`)
   - Login dengan akun tersebut

2. **Set Role Admin di Supabase**:
   - Buka Supabase Dashboard → SQL Editor
   - Jalankan query berikut (ganti `admin` dengan username yang Anda buat):

```sql
-- Set user sebagai admin berdasarkan username
UPDATE profiles 
SET role = 'admin' 
WHERE username = 'admin';
```

3. **Verifikasi**:
   - Logout dari aplikasi
   - Login kembali dengan username `admin`
   - Cek di Navbar → dropdown user → seharusnya ada link "Admin Panel"
   - Klik "Admin Panel" atau akses langsung `/admin`

### Metode 2: Set User Existing Sebagai Admin

Jika Anda sudah punya user yang ingin dijadikan admin:

```sql
-- Ganti 'username_anda' dengan username yang ingin dijadikan admin
UPDATE profiles 
SET role = 'admin' 
WHERE username = 'username_anda';
```

### Metode 3: Cek User yang Sudah Ada

Untuk melihat semua user yang ada:

```sql
-- Lihat semua user
SELECT id, username, full_name, role, created_at 
FROM profiles 
ORDER BY created_at DESC;
```

## Keamanan Admin

### Rekomendasi Keamanan

1. **URL Khusus vs Role Check**:
   - ✅ **Saat ini**: Menggunakan role check (`isAdmin`) - **SUDAH AMAN**
   - ✅ **URL tetap `/admin`** - tidak perlu URL khusus karena sudah ada `AdminRoute` yang protect
   - ✅ **Double protection**: `AdminRoute` + check di `Admin.jsx` component

2. **Best Practices**:
   - Gunakan password yang kuat untuk akun admin
   - Jangan share username/password admin
   - Pertimbangkan untuk membuat multiple admin accounts untuk backup
   - Monitor aktivitas admin melalui logs (jika ada)

3. **Alternatif (Opsional)**:
   Jika ingin lebih aman, bisa tambahkan:
   - URL khusus dengan token: `/admin?token=secret-token` (tidak direkomendasikan karena kurang secure)
   - IP whitelist (jika deploy, bisa diatur di server level)
   - 2FA (Two-Factor Authentication) - perlu implementasi tambahan

## Fitur Admin Page

Setelah login sebagai admin, Anda dapat:

1. **Dashboard**:
   - Melihat statistik: Total Users, Total Reviews, Total Reports, Pending Reports
   - Melihat Recent Reviews (10 terbaru)
   - Melihat Recent Reports (10 terbaru)

2. **Manage Reports**:
   - Approve reports (set status menjadi `reviewed`)
   - Dismiss reports (set status menjadi `dismissed`)

3. **Tabs (Untuk Pengembangan)**:
   - Reviews: Manage semua reviews
   - Reports: Manage semua reports
   - Users: Manage semua users

## Troubleshooting

### Admin Panel Tidak Muncul di Navbar

1. Pastikan user sudah di-set sebagai admin:
```sql
SELECT username, role FROM profiles WHERE username = 'username_anda';
```

2. Logout dan login kembali (untuk refresh `isAdmin` state)

3. Cek console browser untuk error

### Tidak Bisa Akses `/admin`

1. Pastikan sudah login
2. Pastikan role sudah `admin` (cek dengan query di atas)
3. Cek `AdminRoute` component apakah ada error
4. Cek network tab di browser untuk error API

### Error "Akses Ditolak"

- Pastikan user sudah di-set sebagai admin di database
- Refresh halaman atau logout/login kembali

## Quick Setup Script

Jalankan script ini di Supabase SQL Editor untuk setup cepat:

```sql
-- 1. Cek user yang ada
SELECT username, role FROM profiles;

-- 2. Set user sebagai admin (ganti 'admin' dengan username Anda)
UPDATE profiles 
SET role = 'admin' 
WHERE username = 'admin';

-- 3. Verifikasi
SELECT username, role, created_at 
FROM profiles 
WHERE role = 'admin';
```

## Catatan Penting

- **Default role**: Semua user baru otomatis memiliki role `user`
- **Role admin**: Hanya bisa di-set manual melalui SQL query
- **Security**: AdminRoute sudah protect dengan double check (route level + component level)
- **URL**: Tetap menggunakan `/admin` - tidak perlu URL khusus karena sudah aman dengan role check
