# 🔧 useEffect & Supabase Fix Documentation

## 📋 Masalah yang Ditemukan & Diperbaiki

---

## 🔴 **BUG KRITIS #1: `loading === 0`**

### **Kode Lama (BUG):**
```javascript
// Line 616
const shouldShowSkeleton = loading === 0;  // ❌ SELALU FALSE!
```

### **Mengapa Bug:**
- `loading` adalah **BOOLEAN** (`true` atau `false`)
- `loading === 0` membandingkan dengan **NUMBER**
- `true === 0` → `false`
- `false === 0` → `false`
- **Hasil:** Skeleton TIDAK PERNAH muncul!

### **Kode Baru (FIXED):**
```javascript
const showSkeleton = loading && reviews.length === 0;  // ✅ CORRECT
```

---

## 🟡 **MASALAH #2: Kompleksitas Berlebihan**

### **Masalah di Kode Lama:**

1. **5 useEffect yang saling terkait:**
   ```
   useEffect #1: Update reviewsLengthRef
   useEffect #2: Real-time subscription
   useEffect #3: Trigger loadReviews
   useEffect #4: Handle newReview
   ```
   
2. **Complex retry logic dengan AbortController:**
   - Multiple AbortController creation/cleanup
   - Retry loop dengan backoff
   - Race conditions saat cleanup

3. **Cooldown logic yang membingungkan:**
   ```javascript
   if (!forceRefresh && !isFirstLoad && timeSinceLastFetch < cooldownTime) {
     return;  // Bisa block fetch yang valid!
   }
   ```

4. **pendingRequestRef race condition:**
   - Set `true` di awal fetch
   - Jika fetch di-abort, mungkin tetap `true` selamanya
   - Fetch berikutnya di-skip

---

## ✅ **SOLUSI: Rewrite dengan Pendekatan SEDERHANA**

### **Prinsip:**
1. **Satu fetch function yang jelas**
2. **State minimal:** `reviews`, `loading`, `error`
3. **Refs yang jelas:** `isMountedRef`, `abortControllerRef`, `fetchIdRef`
4. **3 useEffect dengan tanggung jawab jelas**

### **Flow Baru:**

```
Component Mount
      ↓
useEffect #1 (placeId change)
      ↓
fetchReviews()
      ↓
  ┌─────────────────┐
  │ Set loading     │
  │ Fetch reviews   │
  │ Fetch profiles  │
  │ Fetch photos    │
  │ Fetch replies   │
  │ Set state       │
  │ Set loading=false│
  └─────────────────┘
      ↓
useEffect #2 (Real-time subscription)
      ↓
On INSERT → refetch
On UPDATE → update local state
On DELETE → remove from local state
      ↓
useEffect #3 (newReview prop)
      ↓
Add to local state + refetch
```

---

## 📊 **Perbandingan Kode Lama vs Baru:**

| Aspek | Kode Lama | Kode Baru |
|-------|-----------|-----------|
| **Lines of Code** | ~800 | ~400 |
| **useEffect** | 5 | 3 |
| **Refs** | 5 | 3 |
| **Retry Logic** | Complex (3 attempts) | None (Supabase handles) |
| **Cooldown** | 500ms with conditions | None |
| **Abort Handling** | Complex | Simple |
| **Race Conditions** | Possible | Prevented with fetchIdRef |
| **Loading State** | Bug (always false) | Correct |

---

## 🔍 **Detail useEffect Baru:**

### **useEffect #1: Initial Fetch**
```javascript
useEffect(() => {
  // Reset state
  isMountedRef.current = true;
  setReviews([]);
  setLoading(true);
  setError(null);
  
  // Fetch data
  fetchReviews();
  
  // Cleanup
  return () => {
    isMountedRef.current = false;
    abortControllerRef.current?.abort();
  };
}, [placeId]); // ONLY placeId
```

**Responsibility:** Fetch data saat mount atau placeId berubah

### **useEffect #2: Real-time Subscription**
```javascript
useEffect(() => {
  const channel = supabase
    .channel(`reviews-${placeId}`)
    .on('postgres_changes', { ... }, (payload) => {
      if (payload.eventType === 'INSERT') {
        fetchReviews(); // Refetch untuk dapat data lengkap
      } else if (payload.eventType === 'UPDATE') {
        setReviews(prev => prev.map(...)); // Update local
      } else if (payload.eventType === 'DELETE') {
        setReviews(prev => prev.filter(...)); // Remove local
      }
    })
    .subscribe();
  
  return () => supabase.removeChannel(channel);
}, [placeId, fetchReviews]);
```

**Responsibility:** Sync dengan database secara real-time

### **useEffect #3: Handle newReview Prop**
```javascript
useEffect(() => {
  if (!newReview?.id) return;
  
  // Optimistic update
  setReviews(prev => [{ ...newReview }, ...prev]);
  
  // Refetch untuk sync
  setTimeout(() => fetchReviews(), 500);
}, [newReview, fetchReviews]);
```

**Responsibility:** Handle review baru dari parent component

---

## 🛡️ **Pencegahan Race Condition:**

### **Problem:**
```
Fetch #1 started → User navigates → Fetch #1 completes → Updates WRONG component
```

### **Solution: fetchIdRef**
```javascript
const fetchIdRef = useRef(0);

const fetchReviews = async () => {
  const currentFetchId = ++fetchIdRef.current;
  
  // ... fetch data ...
  
  // Check if this fetch is still relevant
  if (currentFetchId !== fetchIdRef.current) {
    console.log('Fetch outdated, ignoring result');
    return;
  }
  
  // Safe to update state
  setReviews(data);
};
```

---

## 🧪 **Testing Checklist:**

### **Test 1: Initial Load**
```
1. Open coffee shop detail page
2. Expected: Skeleton shows briefly, then reviews appear
3. Check console: No errors
```

### **Test 2: Refresh (F5)**
```
1. On detail page, press F5
2. Expected: Page reloads, skeleton shows, reviews appear
3. Check console: "🚀 Fetching reviews" log
```

### **Test 3: Navigation**
```
1. Go to coffee shop A
2. Click to coffee shop B
3. Expected: Reviews for B shown (not A)
4. Check console: Fetch for A aborted, Fetch for B succeeds
```

### **Test 4: Add Review**
```
1. Submit new review
2. Expected: Review appears immediately (optimistic)
3. After 500ms: Data syncs with database
```

### **Test 5: Real-time Update**
```
1. Open same coffee shop in 2 tabs
2. Add review in tab 1
3. Expected: Review appears in tab 2 automatically
```

---

## 📝 **RLS Requirements:**

Untuk fetch tanpa error, pastikan RLS policy di Supabase:

```sql
-- Reviews: Public Read
CREATE POLICY "public_read_reviews" ON reviews
FOR SELECT TO public USING (true);

-- Profiles: Public Read
CREATE POLICY "public_read_profiles" ON profiles
FOR SELECT TO public USING (true);

-- Review Photos: Public Read
CREATE POLICY "public_read_photos" ON review_photos
FOR SELECT TO public USING (true);

-- Review Replies: Public Read
CREATE POLICY "public_read_replies" ON review_replies
FOR SELECT TO public USING (true);
```

---

## ✅ **Summary:**

| Before | After |
|--------|-------|
| ❌ Skeleton never shows | ✅ Skeleton shows correctly |
| ❌ Complex retry logic | ✅ Simple direct fetch |
| ❌ 5 useEffects | ✅ 3 useEffects |
| ❌ ~800 lines | ✅ ~400 lines |
| ❌ Race conditions possible | ✅ fetchIdRef prevents |
| ❌ Hard to debug | ✅ Clear flow |

---

**Date:** 2025-12-22  
**Status:** ✅ FIXED  
**Files Changed:** `src/components/ReviewList.jsx`





