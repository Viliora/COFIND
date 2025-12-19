# Perbaikan: Review Hilang dan User Logout Tiba-tiba

## 🔧 Masalah yang Diperbaiki

### **Masalah:**
1. Setelah submit review berhasil dan review tampil
2. Tiba-tiba review section menjadi skeleton (loading)
3. Setelah skeleton selesai, review hilang
4. Akun tiba-tiba logout (dari user mode menjadi guest mode)

### **Penyebab:**
1. **`visibilitychange` listener terlalu agresif** - Trigger re-fetch saat tab menjadi visible
2. **`loadReviews()` selalu clear reviews** - `setReviews([])` di awal menyebabkan review hilang
3. **Error/timeout menyebabkan reviews kosong** - Jika fetch gagal, reviews menjadi empty
4. **AuthContext logout karena error** - Error saat fetch profile menyebabkan logout

---

## 🔄 Perbaikan yang Dibuat

### **1. Hapus `visibilitychange` Listener (Terlalu Agresif)**

**Sebelum:**
```javascript
// Re-fetch when user returns to tab (visibility change)
const handleVisibilityChange = () => {
  if (document.visibilityState === 'visible' && placeId) {
    console.log('[ReviewList] Tab became visible - refreshing reviews');
    loadReviews();
  }
};

document.addEventListener('visibilitychange', handleVisibilityChange);
```

**Masalah:**
- Listener terlalu agresif - trigger re-fetch bahkan saat user tidak melakukan apa-apa
- Menyebabkan review hilang saat tab menjadi visible
- Tidak perlu karena user bisa manual refresh jika diperlukan

**Sesudah:**
```javascript
// NOTE: visibilitychange listener dihapus karena terlalu agresif
// Ini menyebabkan review hilang saat user tidak melakukan apa-apa
// Jika perlu refresh, user bisa manual refresh page
```

**Manfaat:**
- Tidak ada unwanted re-fetch
- Review tidak hilang tiba-tiba
- Better user experience

---

### **2. Prevent Re-fetch Terlalu Sering (Debounce/Throttle)**

**Perbaikan:**
- Add `lastFetchTime` state untuk track waktu fetch terakhir
- Prevent re-fetch jika kurang dari 2 detik dari fetch sebelumnya
- Hanya fetch saat benar-benar diperlukan (placeId change, initial load)

**Code:**
```javascript
const [lastFetchTime, setLastFetchTime] = useState(0);

const loadReviews = async (preserveExisting = false) => {
  // Prevent re-fetch terlalu sering (minimal 2 detik antara fetch)
  const now = Date.now();
  if (!preserveExisting && now - lastFetchTime < 2000) {
    console.log('[ReviewList] Skipping fetch - too soon after last fetch');
    return;
  }
  // ...
  setLastFetchTime(Date.now());
};
```

---

### **3. Preserve Existing Reviews Saat Re-fetch**

**Sebelum:**
```javascript
// Clear previous reviews to ensure fresh data
setReviews([]);
// ... fetch ...
setReviews(mappedReviews); // Replace all reviews
```

**Masalah:**
- Selalu clear reviews di awal
- Jika fetch gagal/timeout, reviews menjadi kosong
- Review baru yang baru ditambahkan hilang

**Sesudah:**
```javascript
// Only clear reviews on initial load or placeId change
// Don't clear if we're just refreshing (preserve existing reviews)
if (!preserveExisting) {
  setReviews([]);
}

// Merge dengan existing reviews jika preserveExisting = true
if (preserveExisting) {
  setReviews(prev => {
    // Merge: keep existing reviews yang tidak ada di fetch baru, add new ones
    const existingIds = new Set(prev.map(r => r.id));
    const newReviews = mappedReviews.filter(r => !existingIds.has(r.id));
    const updatedReviews = prev.map(existing => {
      const updated = mappedReviews.find(r => r.id === existing.id);
      return updated || existing; // Use updated version if exists, otherwise keep existing
    });
    return [...newReviews, ...updatedReviews].sort((a, b) => {
      // Sort by created_at descending
      const dateA = new Date(a.created_at || 0);
      const dateB = new Date(b.created_at || 0);
      return dateB - dateA;
    });
  });
} else {
  setReviews(mappedReviews);
}
```

**Manfaat:**
- Existing reviews tidak hilang saat re-fetch
- Review baru tetap ada meski ada re-fetch
- Merge strategy memastikan data up-to-date tanpa kehilangan data

---

### **4. Fix AuthContext - Jangan Logout pada Error**

**Sebelum:**
```javascript
} catch (authError) {
  console.error('[Auth] Error in onAuthStateChange:', authError);
  // Ensure state is cleared on error
  setUser(null);
  setProfile(null);
}
```

**Masalah:**
- Error (misalnya RLS issue, network timeout) menyebabkan logout
- User tiba-tiba menjadi guest meski masih login
- Tidak user-friendly

**Sesudah:**
```javascript
} catch (authError) {
  console.error('[Auth] Error in onAuthStateChange:', authError);
  // CRITICAL: Don't clear user session on error - might be temporary network/RLS issue
  // Only clear if it's a SIGNED_OUT event or explicit logout
  // This prevents user from being logged out unexpectedly
  if (event === 'SIGNED_OUT') {
    setUser(null);
    setProfile(null);
  } else {
    // Keep existing state - don't logout on error
    console.warn('[Auth] Error occurred but keeping existing session state');
  }
}
```

**Manfaat:**
- User tidak logout karena error
- Session tetap ada meski ada error
- Better user experience

---

## 📋 Langkah Implementasi

### **Langkah 1: Test Submit Review**

1. Login sebagai user
2. Submit review baru
3. **Expected**: 
   - Review muncul langsung
   - Tidak ada skeleton tiba-tiba
   - Review tidak hilang
   - User tetap login

### **Langkah 2: Test Tab Visibility**

1. Buka detail coffee shop dengan review
2. Switch ke tab lain
3. Kembali ke tab
4. **Expected**: 
   - Review tetap ada
   - Tidak ada re-fetch
   - Tidak ada skeleton

### **Langkah 3: Test Error Handling**

1. Simulate network error (Chrome DevTools → Network → Offline)
2. Submit review atau navigate
3. **Expected**: 
   - User tetap login (tidak logout)
   - Error di-log tapi tidak clear session

---

## ✅ Hasil Setelah Perbaikan

### Sebelum:
- ❌ `visibilitychange` listener terlalu agresif
- ❌ Review hilang saat re-fetch
- ❌ User logout karena error
- ❌ Review baru hilang setelah submit

### Sesudah:
- ✅ `visibilitychange` listener dihapus
- ✅ Review tidak hilang saat re-fetch (preserve existing)
- ✅ User tidak logout karena error
- ✅ Review baru tetap ada setelah submit
- ✅ Debounce/throttle prevent re-fetch terlalu sering

---

## 🧪 Testing

### Test Case 1: Submit Review
1. Login sebagai user
2. Submit review baru
3. **Expected**: 
   - Review muncul langsung
   - Tidak ada skeleton tiba-tiba
   - Review tidak hilang
   - User tetap login

### Test Case 2: Tab Switch
1. Buka detail coffee shop dengan review
2. Switch ke tab lain
3. Kembali ke tab
4. **Expected**: 
   - Review tetap ada
   - Tidak ada re-fetch
   - Tidak ada skeleton

### Test Case 3: Network Error
1. Simulate network error
2. Submit review atau navigate
3. **Expected**: 
   - User tetap login
   - Error di-log tapi tidak clear session

### Test Case 4: Multiple Reviews
1. Submit multiple reviews
2. **Expected**: 
   - Semua review tetap ada
   - Tidak ada review yang hilang
   - Tidak ada skeleton tiba-tiba

---

## 📝 Catatan Penting

1. **Visibility Change Listener**:
   - Listener dihapus karena terlalu agresif
   - User bisa manual refresh jika perlu
   - Tidak perlu auto-refresh saat tab visible

2. **Review Preservation**:
   - Reviews di-preserve saat re-fetch
   - Merge strategy memastikan data up-to-date
   - Review baru tidak hilang

3. **Error Handling**:
   - AuthContext tidak logout pada error
   - Session tetap ada meski ada error
   - Better user experience

4. **Debounce/Throttle**:
   - Prevent re-fetch terlalu sering
   - Minimal 2 detik antara fetch
   - Hanya fetch saat benar-benar diperlukan

---

## 🔗 Related Files

- `frontend-cofind/src/components/ReviewList.jsx` - Hapus visibilitychange, preserve reviews (fixed)
- `frontend-cofind/src/context/AuthContext.jsx` - Jangan logout pada error (fixed)

---

## 🎯 Action Items

1. **Test Submit Review** - Pastikan review tidak hilang setelah submit
2. **Test Tab Switch** - Pastikan review tetap ada saat switch tab
3. **Test Error Handling** - Pastikan user tidak logout karena error
4. **Monitor Console** - Pastikan tidak ada unwanted re-fetch
