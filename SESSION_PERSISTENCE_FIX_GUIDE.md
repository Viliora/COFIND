# SESSION PERSISTENCE & 304 NOT MODIFIED FIX - COMPREHENSIVE GUIDE

## Ringkasan Masalah yang Diperbaiki

### 1. **WebSocket HMR Conflict**
- **Masalah**: `ws://localhost:5173/?token=...` menunjukkan WebSocket connection 101 Switching Protocols
- **Penyebab**: Vite HMR (Hot Module Reload) WebSocket tidak explicitly configured, bisa conflict
- **Solusi**: Tambah explicit HMR config di `vite.config.js`

### 2. **304 Not Modified Responses**
- **Masalah**: Banyak request dengan status 304 (Not Modified) di Network tab
- **Penyebab**: Browser cache dan Service Worker caching HTML pages (/) yang sudah di-cache
- **Solusi**: 
  - Disable HTML page caching di Service Worker
  - Force no-cache headers untuk HTML requests
  - Service Worker return cache-busting headers untuk HTML

### 3. **Session Hilang Setelah Refresh**
- **Masalah**: Session invalid/hilang setelah F5 refresh page
- **Penyebab**:
  - devCache.js caching auth endpoints
  - Service Worker caching stale HTML dengan stale session data
  - Supabase session tidak di-restore properly
  - Back-forward cache (bfcache) returning stale page
- **Solusi**: Multiple fixes (lihat detail di bawah)

---

## File yang Diubah & Penjelasan

### 1. **vite.config.js** - Explicit HMR Configuration

```javascript
hmr: {
  protocol: 'ws',         // WebSocket protocol explicit
  host: 'localhost',      // Explicit host
  port: 5173,             // Explicit port (sama dengan dev server)
  timeout: 60000,         // 60s timeout untuk connection
  overlay: true,          // Error overlay
}
```

**Mengapa**: Memastikan Vite HMR tidak ambiguous dan tidak conflict dengan token di WebSocket URL. Dengan explicit config, HMR tahu persis kemana connect tanpa ambiguity.

---

### 2. **src/utils/devCache.js** - Enhanced Auth Detection

Ditambah filter untuk mencegah cache:
- `/session`, `/validate`, `/refresh` endpoints
- User-specific reviews (dengan `user_id` filter)
- Favorites, Want-to-Visit endpoints
- `.html` files (prevent caching app shell)

```javascript
function isAuthRelated(url) {
  // EXTENDED dengan tambahan 20+ patterns untuk catch auth/session URLs
  // Tujuan: TIDAK CACHE apapun yang auth-related
}
```

**Mengapa**: devCache.js sebelumnya hanya block `/auth/`, `/session`, `/profile`, `/user`. Tapi masih bisa cache `/reviews?user_id=...` dan favorites. Extended filter memastikan SEMUA user-specific data tidak di-cache.

---

### 3. **public/sw.js** - Service Worker Cache Strategy Overhaul

#### Perubahan Major:

**A. CACHE VERSION: v5 → v6**
```javascript
const CACHE_VERSION = 'cofind-v6';  // Force clean cache
```
Saat users load page, browser akan delete old v5 cache dan download v6 baru.

**B. HTML Pages: Network Only (TIDAK DI-CACHE)**
```javascript
// SHELL_ASSETS dihapus / dihapus dari pre-cache
// / dan /index.html TIDAK di-cache lagi

if (isHTMLRequest(request)) {
  event.respondWith(networkOnlyStrategyForHTML(request));
}
```

**C. networkOnlyStrategyForHTML Strategy**
```javascript
// Add cache-busting headers
'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0'
'If-Modified-Since': '0'  // Prevent 304 responses
'If-None-Match': '*'       // Prevent 304 responses

// Add query param
url.searchParams.set('_html_t', Date.now().toString())

// Result: Always fetch fresh HTML, never cache, prevent 304s
```

**Mengapa**: Service Worker caching HTML pages = stale app shell dengan stale session data. Dengan Network Only, browser SELALU fetch HTML fresh dari server, memastikan session up-to-date dan prevent 304 responses.

**D. Enhanced isHTMLRequest Detection**
```javascript
function isHTMLRequest(request) {
  return (
    accept.includes('text/html') ||  // Browser requesting HTML
    pathname.endsWith('.html') ||     // .html files
    (!pathname.includes('.') && !pathname.startsWith('/api/'))  // Routes
  );
}
```

---

### 4. **src/lib/supabase.js** - Session Handling Improvements

#### A. Supabase Client Init dengan Cache Control Headers
```javascript
global: {
  headers: {
    'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
    'Pragma': 'no-cache',
    'Expires': '0',
  },
}
```

#### B. Enhanced Auth Config
```javascript
auth: {
  persistSession: true,
  autoRefreshToken: true,
  detectSessionInUrl: true,
  flowType: 'implicit',
  storage: localStorage,  // Explicit storage
}
```

#### C. New Functions: forceSessionValidation
```javascript
export const forceSessionValidation = async () => {
  // Force fetch dari server, clear localStorage cache
  // Check token expiry
  // Auto-refresh jika expire soon
  // Return: { valid, user, session }
}
```

**Mengapa**: 
- Aggressive no-cache headers memastikan Supabase API response tidak di-cache browser
- forceSessionValidation untuk use-cases dimana session perlu di-validate ulang (e.g., refresh page)

---

### 5. **src/utils/sessionFix.js** - NEW FILE

Utility komprehensif untuk session persistence:

```javascript
// 1. clearAuthRelatedCache()
// Clear devCache entries yang auth/session related

// 2. clearOldServiceWorkerCaches()
// Delete SW cache dari v5 dan version lama lainnya

// 3. setAggressiveCacheControl()
// Inject meta tags dinamis, disable bfcache

// 4. detectBackForwardCache()
// Detect jika page di-load dari browser bfcache
// Auto-reload jika detect bfcache (stale session)

// 5. initializeSessionFix()
// Main init function - call di App.jsx
```

**Mengapa**: Centralize semua session-related fixes di satu file. Dipanggil di App.jsx useEffect saat app initialize.

---

### 6. **src/App.jsx** - Integration

```javascript
import { initializeSessionFix } from './utils/sessionFix';

function App() {
  useEffect(() => {
    initializeSessionFix();  // Call saat app load
  }, []);
  // ...
}
```

---

## Masalah & Root Causes

### Problem: 304 Not Modified Responses

**Root Causes:**
1. Service Worker caching `/index.html` dengan stale content
2. Browser cache headers tidak aggressive enough
3. If-Modified-Since / If-None-Match headers tidak di-bypass

**Fixes:**
- Remove HTML dari SW cache
- Add cache-busting query param: `?_html_t=123456`
- Set If-Modified-Since: '0' dan If-None-Match: '*'
- Set Cache-Control: 'no-cache, no-store, must-revalidate, max-age=0'

---

### Problem: Session Rusak Setelah Refresh

**Root Causes:**
1. **devCache.js** caching session/profile endpoints
2. **Service Worker** returning stale HTML dengan stale session state
3. **Back-forward cache** (bfcache) returning page dari memory tanpa re-authenticate
4. Supabase session tidak di-restore saat page reload

**Fixes:**
- devCache.js: Extend isAuthRelated() untuk block lebih banyak URLs
- Service Worker: networkOnlyStrategyForHTML untuk HTML pages
- sessionFix.js: detectBackForwardCache() untuk reload jika stale
- supabase.js: forceSessionValidation() untuk aggressive session check

---

### Problem: WebSocket Token di URL

**Root Cause:** Vite HMR WebSocket tidak explicitly configured

**Symptom:** `ws://localhost:5173/?token=...`

**Explanation:** 
- Vite HMR WebSocket NORMAL behavior untuk Hot Module Reload
- Token di URL BUKAN auth token, tapi Vite internal mechanism
- Tapi ambiguous config bisa cause conflict

**Fix:** Explicit HMR config di vite.config.js mencegah ambiguity

---

## Testing Steps

### 1. Clear Cache Thoroughly
```powershell
# Close browser completely
# Go to: devtools > Application > Clear site data
# Clear localStorage, sessionStorage, cookies, service worker cache
```

### 2. Login Fresh
1. Go to http://localhost:5173
2. Click Login
3. Enter credentials
4. Should see "User logged in" + profile appears

### 3. Refresh Page (Critical Test)
1. Press F5 atau Ctrl+R
2. **Expected**: Session persists, page loads immediately, user still logged in
3. **Check DevTools Network**:
   - HTML request should be 200, not 304
   - No "from cache" indicator pada HTML
   - Supabase API calls should be fresh (not cached)
4. **Check Console**:
   - No auth errors
   - "Valid session found" log messages

### 4. Check for 304 Responses
DevTools → Network Tab → Filter by "All"
- Should see minimal 304s
- HTML page (/) should be **200**, not 304
- Static assets (JS, CSS) OK to be 304

### 5. Back-Forward Navigation
1. Login → Go to some shop → Click browser back
2. **Expected**: Session still valid, not showing login page
3. Should reload fresh, not from bfcache

### 6. Hard Refresh (Ctrl+Shift+R)
1. Hard refresh page
2. Should clear ALL caches
3. Session should re-validate from Supabase

---

## Debugging Commands

### Check Service Worker Cache
```javascript
// Di DevTools Console
caches.keys().then(names => {
  names.forEach(name => console.log('Cache:', name));
  Promise.all(names.map(name => caches.open(name)
    .then(cache => cache.keys()
    .then(reqs => console.log(name, ':', reqs.map(r => r.url))))));
});
```

### Check localStorage
```javascript
// Cari devCache entries
Object.keys(localStorage)
  .filter(k => k.startsWith('cofind_dev_cache_'))
  .forEach(k => console.log(k, localStorage[k].substring(0, 100)));
```

### Check Supabase Session
```javascript
import { supabase, forceSessionValidation } from './lib/supabase';

// Manual check
const { data: { session } } = await supabase.auth.getSession();
console.log('Current session:', session);

// Force validation
const validation = await forceSessionValidation();
console.log('Force validation:', validation);
```

### Monitor Session Changes
```javascript
// Di App.jsx atau anywhere
import { supabase } from './lib/supabase';

supabase.auth.onAuthStateChange((event, session) => {
  console.log('[Auth] Event:', event, '| Session valid:', !!session?.user);
});
```

---

## Potential Issues & Solutions

### Issue: Masih ada 304 responses
- **Solution**: Hard refresh (Ctrl+Shift+R) untuk clear browser cache
- **Solution**: Check if old Service Worker still cached - update CACHE_VERSION

### Issue: Session still lost after refresh
- **Solution**: Check console untuk error messages dari sessionFix.js
- **Solution**: Verify Supabase environment variables ada
- **Solution**: Check if using localStorage (not session storage)

### Issue: Page load masih slow
- **Solution**: Check Network tab - are static assets being cached? (OK, should be 304)
- **Solution**: If HTML is 304, means browser cache intact - is that correct?

### Issue: Can't login
- **Solution**: Check if Supabase configured properly
- **Solution**: Check browser console untuk auth error messages
- **Solution**: Clear all site data dan try again

---

## Summary of All Changes

| File | Changes | Purpose |
|------|---------|---------|
| vite.config.js | Explicit HMR config | Prevent WebSocket ambiguity |
| src/utils/devCache.js | Extended isAuthRelated() | Don't cache auth/session URLs |
| public/sw.js | Remove HTML from cache, networkOnlyStrategyForHTML | Always fresh HTML, prevent 304s |
| src/lib/supabase.js | Cache-control headers, forceSessionValidation() | Aggressive no-cache, force validation |
| src/App.jsx | Import & call initializeSessionFix() | Initialize fixes on app load |
| src/utils/sessionFix.js | NEW - centralize all fixes | Clear caches, detect bfcache |

---

## Expected Results

✅ **After applying all fixes:**
1. Login, refresh page → Session persists
2. No more "session invalid" errors
3. Network tab shows HTML as 200, not 304
4. No devCache entries untuk auth URLs
5. Service Worker cache clean (v6 only)
6. Back-forward navigation works correctly
7. Dev experience smooth dengan HMR working properly

---

## Deployment Checklist

- [ ] Update vite.config.js dengan HMR config
- [ ] Test HMR works (change component, should auto-reload)
- [ ] Clear browser cache completely (Ctrl+Shift+R)
- [ ] Test login/refresh workflow
- [ ] Check Network tab untuk 200 HTML responses
- [ ] Verify no auth errors di console
- [ ] Test on different browsers (Chrome, Firefox, Safari)
- [ ] Test on incognito/private mode
- [ ] Check mobile devices jika applicable
