# ⚡ Quick Fix: Chrome Cache Issue

## 🚀 Solusi Tercepat (30 detik)

### Di Browser Console Chrome (F12):

```javascript
// Copy-paste script ini dan tekan Enter
(async () => {
  // 1. Unregister Service Worker
  if ('serviceWorker' in navigator) {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(registrations.map(r => r.unregister()));
    console.log('✅ Service Workers unregistered');
  }
  
  // 2. Clear all caches
  if ('caches' in window) {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map(name => caches.delete(name)));
    console.log('✅ Caches cleared:', cacheNames);
  }
  
  // 3. Clear storage
  localStorage.clear();
  sessionStorage.clear();
  console.log('✅ Storage cleared');
  
  // 4. Hard reload
  console.log('🔄 Reloading...');
  window.location.reload(true);
})();
```

---

## 🎯 Atau Gunakan Hard Refresh

**Tekan**: `Ctrl + Shift + R` (Windows/Linux) atau `Cmd + Shift + R` (Mac)

---

## ✅ Setelah Itu

1. Buka halaman detail coffee shop
2. Cek apakah reviews tampil dengan benar
3. Tidak ada "Invalid Date"

Jika masih tidak berubah, coba **Solusi 2** di `FIX_CHROME_CACHE.md`
