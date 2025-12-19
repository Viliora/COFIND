# Cara Membersihkan Session Admin yang Masih Tersimpan

Jika Anda sudah menghapus admin dari database tapi masih ter-login sebagai admin di web, ikuti langkah berikut:

## 🔧 Solusi 1: Clear Session di Browser (Cara Cepat)

### Di Browser Console (F12):

```javascript
// 1. Clear semua Supabase session
localStorage.clear();
sessionStorage.clear();

// 2. Set logout flag
localStorage.setItem('cofind_user_logged_out', 'true');

// 3. Reload halaman
window.location.reload();
```

### Atau gunakan script yang lebih spesifik:

```javascript
// Clear hanya Supabase keys
const allKeys = [];
for (let i = 0; i < localStorage.length; i++) {
  const key = localStorage.key(i);
  if (key && (
    key.includes('supabase') || 
    key.includes('sb-') || 
    key.match(/auth-token/i) ||
    key.match(/^sb-[a-z0-9-]+-auth-token$/i)
  )) {
    allKeys.push(key);
  }
}
allKeys.forEach(key => localStorage.removeItem(key));
sessionStorage.clear();

// Set logout flag
localStorage.setItem('cofind_user_logged_out', 'true');

// Reload
window.location.reload();
```

---

## 🔧 Solusi 2: Hapus dari Supabase Auth (Permanen)

Jika admin masih ada di `auth.users` tapi sudah dihapus dari `profiles`:

### Di Supabase SQL Editor:

```sql
-- 1. Cek apakah admin masih ada di auth.users
SELECT id, email, created_at 
FROM auth.users 
WHERE email LIKE '%@cofind.app' 
ORDER BY created_at DESC;

-- 2. Hapus dari auth.users (akan cascade ke semua data terkait)
-- GANTI 'admin@cofind.app' dengan email admin yang ingin dihapus
DELETE FROM auth.users 
WHERE email = 'admin@cofind.app';

-- Atau hapus berdasarkan username (jika masih ada di profiles)
DELETE FROM auth.users 
WHERE id = (SELECT id FROM profiles WHERE username = 'admin');
```

---

## 🔧 Solusi 3: Pastikan Profile Benar-Benar Terhapus

### Cek di Supabase:

```sql
-- 1. Cek apakah masih ada profile admin
SELECT id, username, role, created_at 
FROM profiles 
WHERE role = 'admin' OR username = 'admin';

-- 2. Jika masih ada, hapus
DELETE FROM profiles 
WHERE username = 'admin' OR role = 'admin';
```

---

## ✅ Verifikasi Setelah Clear Session

1. **Buka Browser Console (F12)**
2. **Jalankan script clear session** (Solusi 1)
3. **Refresh halaman**
4. **Cek apakah sudah guest mode**:
   - Navbar seharusnya menampilkan "Masuk" bukan dropdown user
   - Tidak bisa akses `/admin`
   - Tidak ada data user di localStorage

---

## 🐛 Jika Masih Masalah

Jika setelah clear session masih ter-login sebagai admin:

1. **Cek apakah admin masih ada di database**:
   ```sql
   SELECT * FROM profiles WHERE username = 'admin';
   SELECT * FROM auth.users WHERE email LIKE '%admin%';
   ```

2. **Clear semua storage**:
   ```javascript
   // Di browser console
   localStorage.clear();
   sessionStorage.clear();
   location.reload();
   ```

3. **Cek Network Tab**:
   - Buka DevTools → Network
   - Refresh halaman
   - Cek apakah ada request ke Supabase yang masih return session

4. **Hard Refresh**:
   - `Ctrl + Shift + R` (Windows/Linux)
   - `Cmd + Shift + R` (Mac)

---

## 📝 Catatan

- **Session Supabase** disimpan di `localStorage` browser
- **Profile** disimpan di database table `profiles`
- Jika profile dihapus tapi session masih ada, aplikasi sekarang akan **otomatis clear session** saat detect profile tidak ada
- Perubahan ini sudah diimplementasikan di `AuthContext.jsx`

---

## 🔄 Setelah Clear Session, Buat Admin Baru

Jika ingin membuat admin baru:

```sql
-- 1. Buat user baru (atau gunakan user yang sudah ada)
-- 2. Set role menjadi admin
UPDATE profiles 
SET role = 'admin' 
WHERE username = 'username_baru';
```
