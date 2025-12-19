# Panduan Verifikasi Authentication & Session Management

## 📋 Overview

Dokumen ini menjelaskan bagaimana sistem authentication dan session management bekerja di aplikasi CoFind, serta cara memverifikasi bahwa semuanya berfungsi dengan benar.

---

## 🔐 1. Status Pengguna (Login/Logout)

### A. Komponen yang Memeriksa Status Login

#### ✅ **Protected Routes (Middleware Routing)**

**Lokasi:** `src/components/ProtectedRoute.jsx` dan `src/components/AdminRoute.jsx`

**Fungsi:**
- `ProtectedRoute`: Melindungi route yang memerlukan login (contoh: `/profile`)
- `AdminRoute`: Melindungi route yang memerlukan role admin (contoh: `/admin`)

**Cara Kerja:**
1. Mengecek `initialized` dan `loading` dari `AuthContext`
2. Menampilkan loading screen jika masih memeriksa auth
3. Redirect ke `/login` jika user tidak authenticated
4. Untuk `AdminRoute`, juga mengecek `isAdmin` dan redirect ke `/` jika bukan admin

**Routes yang Dilindungi:**
```jsx
// src/App.jsx
<Route 
  path="/profile" 
  element={
    <ProtectedRoute>
      <Profile />
    </ProtectedRoute>
  } 
/>
<Route 
  path="/admin" 
  element={
    <AdminRoute>
      <Admin />
    </AdminRoute>
  } 
/>
```

#### ✅ **Komponen dengan Conditional Rendering**

Komponen berikut menggunakan `useAuth()` untuk conditional rendering:

1. **Navbar** (`src/components/Navbar.jsx`)
   - Menampilkan "Masuk" jika guest
   - Menampilkan dropdown user jika authenticated
   - Menampilkan "Admin Panel" link jika `isAdmin === true`

2. **ShopDetail** (`src/pages/ShopDetail.jsx`)
   - Menyembunyikan Favorite/Want to Visit buttons untuk guest
   - Menampilkan review form hanya untuk authenticated users

3. **Favorite** (`src/pages/Favorite.jsx`)
   - Menampilkan login prompt untuk guest
   - Menampilkan favorite list untuk authenticated users

4. **WantToVisit** (`src/pages/WantToVisit.jsx`)
   - Menampilkan login prompt untuk guest
   - Menampilkan want-to-visit list untuk authenticated users

5. **ReviewForm** (`src/components/ReviewForm.jsx`)
   - Hanya render jika `isAuthenticated === true`

6. **ReviewCard** (`src/components/ReviewCard.jsx`)
   - Menampilkan edit/delete buttons hanya untuk owner
   - Menampilkan reply button hanya untuk authenticated users

---

## 🗄️ 2. Session & Token Storage

### A. Lokasi Penyimpanan

**Supabase menyimpan session di:**
- `localStorage`: Session token dan metadata
- `sessionStorage`: Session sementara (opsional)

**Key yang digunakan oleh Supabase:**
- `sb-{project-ref}-auth-token`: Session token utama
- `cofind_user_logged_out`: Custom flag untuk logout (dibuat oleh aplikasi)

### B. Proses Logout (Pembersihan Storage)

**Lokasi:** `src/context/AuthContext.jsx` → `signOut()`

**Proses:**
1. Set flag `cofind_user_logged_out = 'true'` di localStorage
2. Clear state (`setUser(null)`, `setProfile(null)`)
3. Panggil `supabase.auth.signOut({ scope: 'global' })`
4. Hapus semua key Supabase dari localStorage:
   - Semua key yang mengandung `supabase`
   - Semua key yang mengandung `sb-`
   - Semua key yang match pattern `auth-token`
5. Clear `sessionStorage`
6. Restore flag `cofind_user_logged_out` (agar tetap ada)

**Verifikasi:**
```javascript
// Buka browser console setelah logout
console.log('Logout flag:', localStorage.getItem('cofind_user_logged_out')); // Should be 'true'
console.log('Supabase keys:', Object.keys(localStorage).filter(k => k.includes('supabase') || k.includes('sb-'))); // Should be empty
```

---

## 👤 3. Verifikasi Peran Pengguna (Role)

### A. Cara Kerja

**Lokasi:** `src/context/AuthContext.jsx`

**Proses:**
1. Saat user login, `fetchProfile()` dipanggil
2. Profile data diambil dari table `profiles` di Supabase
3. Field `role` (bisa `'user'` atau `'admin'`) disimpan di state
4. `isAdmin` dihitung dari `profile?.role === 'admin'`

**State yang Tersedia:**
```javascript
const { 
  user,           // User object dari Supabase Auth
  profile,        // Profile object dari table profiles (termasuk role)
  isAuthenticated, // Boolean: true jika user logged in
  isAdmin         // Boolean: true jika profile.role === 'admin'
} = useAuth();
```

### B. Verifikasi Setelah Refresh

**Lokasi:** `src/context/AuthContext.jsx` → `initAuth()`

**Proses:**
1. Saat aplikasi load, `initAuth()` dipanggil
2. Mengecek `cofind_user_logged_out` flag:
   - Jika `true`: Force guest mode, tidak restore session
   - Jika `false` atau tidak ada: Lanjut ke step 3
3. Mengecek session di Supabase:
   - Jika ada session: Restore user dan fetch profile (termasuk role)
   - Jika tidak ada: Set guest mode
4. Profile (termasuk role) di-fetch dari database setiap kali session di-restore

**Verifikasi:**
```javascript
// Buka browser console setelah refresh
const { profile, isAdmin } = useAuth();
console.log('Profile:', profile);
console.log('Role:', profile?.role);
console.log('Is Admin:', isAdmin);
```

---

## 🔄 4. Auto-Login (Session Restoration)

### A. Pengaturan Auto-Login

**Lokasi:** `src/context/AuthContext.jsx` → `initAuth()`

**Kondisi Auto-Login:**
1. ✅ **Aktif secara default** jika:
   - Tidak ada flag `cofind_user_logged_out`
   - Ada valid session di Supabase
   - Session masih valid (user masih ada di database)

2. ❌ **Nonaktif jika:**
   - Flag `cofind_user_logged_out === 'true'` (user explicitly logged out)
   - Environment variable `VITE_DISABLE_AUTO_LOGIN === 'true'`
   - Session tidak valid atau user tidak ada di database

### B. Environment Variable untuk Disable Auto-Login

**File:** `.env` atau `.env.local`

```env
# Nonaktifkan auto-login (untuk development/testing)
VITE_DISABLE_AUTO_LOGIN=true
```

**Catatan:** Jika ini di-set, aplikasi akan selalu start dalam guest mode, bahkan jika ada valid session.

### C. Verifikasi Auto-Login

**Test Case 1: Normal Auto-Login**
1. Login sebagai user/admin
2. Refresh halaman
3. ✅ **Expected:** User tetap logged in dengan role yang sama

**Test Case 2: Logout Flag Active**
1. Login sebagai user/admin
2. Klik logout
3. Refresh halaman
4. ✅ **Expected:** User dalam guest mode (tidak auto-login)

**Test Case 3: Session Expired**
1. Login sebagai user/admin
2. Hapus session di Supabase Dashboard (atau tunggu expired)
3. Refresh halaman
4. ✅ **Expected:** User dalam guest mode

---

## ✅ Checklist Verifikasi

### 1. Status Pengguna
- [ ] Protected routes (`/profile`, `/admin`) redirect ke `/login` jika guest
- [ ] Guest tidak bisa mengakses fitur yang memerlukan login
- [ ] Authenticated users bisa mengakses semua fitur sesuai role
- [ ] Navbar menampilkan UI yang sesuai dengan status login

### 2. Session Storage
- [ ] Setelah logout, semua Supabase keys dihapus dari localStorage
- [ ] Flag `cofind_user_logged_out` tetap ada setelah logout
- [ ] SessionStorage dibersihkan setelah logout
- [ ] Setelah login, flag `cofind_user_logged_out` dihapus

### 3. Verifikasi Role
- [ ] User dengan role `'user'` tidak bisa akses `/admin`
- [ ] User dengan role `'admin'` bisa akses `/admin`
- [ ] Role di-fetch dari database setiap kali session di-restore
- [ ] `isAdmin` state update setelah login/logout

### 4. Auto-Login
- [ ] Auto-login bekerja setelah refresh (jika tidak logout)
- [ ] Auto-login tidak bekerja setelah explicit logout
- [ ] Auto-login tidak bekerja jika session expired
- [ ] Auto-login bisa di-disable dengan environment variable

---

## 🛠️ Utility Functions untuk Debugging

### A. Check Session Storage

Buka browser console dan jalankan:

```javascript
// Check semua Supabase-related keys
const supabaseKeys = Object.keys(localStorage).filter(k => 
  k.includes('supabase') || k.includes('sb-') || k.match(/auth-token/i)
);
console.log('Supabase keys:', supabaseKeys);
console.log('Logout flag:', localStorage.getItem('cofind_user_logged_out'));

// Check sessionStorage
console.log('SessionStorage keys:', Object.keys(sessionStorage));
```

### B. Check Auth State

Di komponen React, tambahkan:

```javascript
import { useAuth } from '../context/AuthContext';

const MyComponent = () => {
  const { user, profile, isAuthenticated, isAdmin, loading, initialized } = useAuth();
  
  useEffect(() => {
    console.log('Auth State:', {
      user: user?.id,
      profile: profile?.username,
      role: profile?.role,
      isAuthenticated,
      isAdmin,
      loading,
      initialized
    });
  }, [user, profile, isAuthenticated, isAdmin, loading, initialized]);
  
  // ... rest of component
};
```

### C. Manual Clear Session (Emergency)

Jika ada masalah dengan session, jalankan di console:

```javascript
// Clear semua Supabase keys
Object.keys(localStorage).forEach(key => {
  if (key.includes('supabase') || key.includes('sb-') || key.match(/auth-token/i)) {
    localStorage.removeItem(key);
  }
});
sessionStorage.clear();

// Set logout flag
localStorage.setItem('cofind_user_logged_out', 'true');

// Reload page
window.location.reload();
```

---

## 🐛 Troubleshooting

### Masalah: User tetap logged in setelah logout

**Penyebab:**
- Flag `cofind_user_logged_out` tidak di-set
- Session tidak di-clear dengan benar
- `onAuthStateChange` restore session meskipun flag aktif

**Solusi:**
1. Cek flag di console: `localStorage.getItem('cofind_user_logged_out')`
2. Cek Supabase keys: `Object.keys(localStorage).filter(k => k.includes('sb-'))`
3. Pastikan `signOut()` di `AuthContext.jsx` sudah benar
4. Pastikan `initAuth()` mengecek flag sebelum restore session

### Masalah: Role tidak update setelah refresh

**Penyebab:**
- Profile tidak di-fetch setelah session restore
- Cache issue

**Solusi:**
1. Cek apakah `fetchProfile()` dipanggil di `initAuth()`
2. Cek apakah `onAuthStateChange` memanggil `fetchProfile()`
3. Clear cache dan refresh

### Masalah: Auto-login tidak bekerja

**Penyebab:**
- Flag `cofind_user_logged_out` masih aktif
- Session expired
- Environment variable `VITE_DISABLE_AUTO_LOGIN` di-set

**Solusi:**
1. Cek flag: `localStorage.getItem('cofind_user_logged_out')`
2. Cek session: `supabase.auth.getSession()`
3. Cek environment variable

---

## 📝 Catatan Penting

1. **Flag `cofind_user_logged_out`** adalah custom flag yang dibuat aplikasi untuk mencegah auto-login setelah explicit logout. Flag ini tidak dihapus oleh Supabase.

2. **Session Supabase** bisa di-restore oleh Supabase SDK secara otomatis. Aplikasi menggunakan flag untuk mencegah ini setelah logout.

3. **Role check** dilakukan di database (table `profiles`), bukan di localStorage. Ini memastikan role selalu up-to-date.

4. **ProtectedRoute dan AdminRoute** adalah middleware yang memeriksa auth sebelum render component. Ini lebih aman daripada hanya conditional rendering di component.

---

## 🔗 File Terkait

- `src/context/AuthContext.jsx` - Core authentication logic
- `src/components/ProtectedRoute.jsx` - Route protection untuk authenticated users
- `src/components/AdminRoute.jsx` - Route protection untuk admin users
- `src/App.jsx` - Route configuration
- `frontend-cofind/supabase-schema-safe.sql` - Database schema (termasuk table profiles dengan role)

