# Session Persistence: Tab Close vs Browser Close

## 🔧 Konfigurasi Session Persistence

### **Requirement:**
1. **Tab Close**: Session tetap ada (tidak hilang) - User tetap login
2. **Browser Close**: Session hilang (logout) - User jadi guest

### **Solusi:**
- Menggunakan `localStorage` untuk session persistence (persist setelah tab close)
- Menggunakan `sessionStorage` sebagai flag untuk detect browser close
- Clear session saat detect new browser session

---

## 🔄 Implementasi

### **1. Supabase Configuration**

Session dikonfigurasi untuk persist di localStorage:

```javascript
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true, // CRITICAL: Session persists in localStorage
    autoRefreshToken: true, // Auto-refresh token to keep session alive
    detectSessionInUrl: true, // Detect session from URL
    storage: typeof window !== 'undefined' ? window.localStorage : undefined,
    storageKey: 'sb-auth-token', // Default storage key
  },
});
```

### **2. Browser Session Detection**

Menggunakan `sessionStorage` sebagai flag untuk detect browser close:

```javascript
// Detect if this is a new browser session
const isNewBrowserSession = !sessionStorage.getItem('cofind_browser_session');

if (isNewBrowserSession) {
  // Browser was closed - clear session
  // Clear Supabase session
  // Clear all Supabase-related storage
  // Set state to guest mode
} else {
  // Tab was closed, but browser is still open - session persists
  // Continue with normal auth initialization
}
```

### **3. Session Flag Management**

- **`cofind_browser_session`** di `sessionStorage`:
  - Set saat component mount
  - Persist across tab close
  - Cleared saat browser close
  - Digunakan untuk detect new browser session

---

## 📋 Perilaku Session

### **Tab Close:**
- ✅ `sessionStorage` tetap ada (flag `cofind_browser_session` masih ada)
- ✅ Session tetap ada di localStorage
- ✅ User tetap login setelah buka tab baru
- ✅ Session tidak hilang

### **Browser Close:**
- ❌ `sessionStorage` di-clear (flag `cofind_browser_session` hilang)
- ❌ Session di-clear dari localStorage
- ❌ User jadi guest setelah buka browser lagi
- ❌ Session hilang

---

## 🚀 Langkah Implementasi

### **Langkah 1: Test Tab Close**

1. Login sebagai user
2. Close tab browser (jangan close browser)
3. Buka tab baru dengan URL yang sama
4. **Expected**: 
   - User tetap login
   - Session tidak hilang
   - Navbar menampilkan username (bukan "Masuk")

### **Langkah 2: Test Browser Close**

1. Login sebagai user
2. Close browser completely (semua tab)
3. Buka browser lagi
4. **Expected**: 
   - User dalam mode guest
   - Session hilang
   - Navbar menampilkan "Masuk"

### **Langkah 3: Verify Session Flag**

1. Login sebagai user
2. Check `sessionStorage.getItem('cofind_browser_session')`
3. **Expected**: 
   - Flag ada (value: 'true')
   - Flag persist setelah tab close
   - Flag hilang setelah browser close

---

## ✅ Hasil Setelah Implementasi

### Tab Close:
- ✅ Session tetap ada di localStorage
- ✅ User tetap login setelah buka tab baru
- ✅ Session tidak hilang
- ✅ Flag `cofind_browser_session` tetap ada

### Browser Close:
- ✅ Session di-clear dari localStorage
- ✅ User jadi guest setelah buka browser lagi
- ✅ Session hilang
- ✅ Flag `cofind_browser_session` hilang (new browser session)

---

## 🧪 Testing

### Test Case 1: Tab Close
1. Login sebagai user
2. Close tab browser (jangan close browser)
3. Buka tab baru
4. **Expected**: 
   - User tetap login
   - Session tidak hilang
   - Navbar menampilkan username

### Test Case 2: Browser Close
1. Login sebagai user
2. Close browser completely
3. Buka browser lagi
4. **Expected**: 
   - User dalam mode guest
   - Session hilang
   - Navbar menampilkan "Masuk"

### Test Case 3: Multiple Tabs
1. Login sebagai user
2. Buka beberapa tab dengan aplikasi yang sama
3. Close salah satu tab
4. **Expected**: 
   - User tetap login di tab lain
   - Session tidak hilang
   - Navbar menampilkan username

### Test Case 4: Browser Restart
1. Login sebagai user
2. Restart browser (close dan buka lagi)
3. **Expected**: 
   - User dalam mode guest
   - Session hilang
   - Navbar menampilkan "Masuk"

---

## 📝 Catatan Penting

1. **sessionStorage Behavior**:
   - `sessionStorage` persist across tab close (dalam browser yang sama)
   - `sessionStorage` cleared saat browser close
   - Digunakan sebagai flag untuk detect browser close

2. **localStorage Behavior**:
   - `localStorage` persist across browser sessions (default)
   - Session di-clear secara manual saat detect new browser session
   - Digunakan untuk store Supabase session

3. **Browser Session Detection**:
   - Menggunakan `sessionStorage.getItem('cofind_browser_session')` untuk detect
   - Jika flag tidak ada = new browser session (browser was closed)
   - Jika flag ada = existing browser session (tab was closed)

4. **Session Clearing**:
   - Session di-clear saat detect new browser session
   - Semua Supabase-related keys dihapus dari localStorage
   - User state di-set ke null (guest mode)

---

## 🔗 Related Files

- `frontend-cofind/src/lib/supabase.js` - Supabase client configuration (fixed)
- `frontend-cofind/src/context/AuthContext.jsx` - Browser session detection (fixed)

---

## 🎯 Action Items

1. **Test Tab Close** - Pastikan session tetap ada setelah tab close
2. **Test Browser Close** - Pastikan session hilang setelah browser close
3. **Test Multiple Tabs** - Pastikan session persist across tabs
4. **Verify Session Flag** - Pastikan flag bekerja dengan benar

---

## 🔧 Troubleshooting

### Masalah: Session Masih Ada Setelah Browser Close

**Solusi:**
1. **Cek sessionStorage**: Pastikan `sessionStorage` di-clear saat browser close
2. **Cek Browser Session Detection**: Pastikan logic detect new browser session bekerja
3. **Cek Console**: Lihat log untuk melihat apakah session di-clear
4. **Cek Browser**: Pastikan browser benar-benar close (semua tab)

### Masalah: Session Hilang Setelah Tab Close

**Solusi:**
1. **Cek sessionStorage**: Pastikan `sessionStorage` tidak di-clear saat tab close
2. **Cek Browser Session Detection**: Pastikan logic tidak salah detect tab close sebagai browser close
3. **Cek Console**: Lihat log untuk melihat apakah session di-clear
4. **Cek Browser**: Pastikan hanya tab yang di-close (bukan browser)

### Masalah: Flag Tidak Bekerja

**Solusi:**
1. **Cek sessionStorage**: Pastikan browser support sessionStorage
2. **Cek Flag Setting**: Pastikan flag di-set saat component mount
3. **Cek Flag Clearing**: Pastikan flag di-clear saat browser close
4. **Cek Console**: Lihat log untuk melihat apakah flag di-set/di-clear
