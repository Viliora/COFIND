# QUICK DIAGNOSIS: Jika Session Masih Rusak Setelah Fix

## Diagnosis Flow

### Step 1: Verify Fixes Applied

Run di terminal (di root project):
```powershell
# 1. Check vite.config.js
grep "protocol: 'ws'" frontend-cofind/vite.config.js
# Expected output: protocol: 'ws',

# 2. Check devCache.js extended
grep "endsWith('.html')" frontend-cofind/src/utils/devCache.js
# Expected: 1+ matches (should include .html filter)

# 3. Check Service Worker v6
grep "CACHE_VERSION = 'cofind-v6'" frontend-cofind/public/sw.js
# Expected: 1 match for v6

# 4. Check sessionFix.js exists
ls frontend-cofind/src/utils/sessionFix.js
# Expected: File exists

# 5. Check App.jsx integration
grep "initializeSessionFix" frontend-cofind/src/App.jsx
# Expected: 1+ matches
```

**If any check fails**: File belum ter-update. Re-read from git atau apply manual fixes.

---

### Step 2: Check Browser Cache State

Run di DevTools Console:
```javascript
// 1. Check Service Worker cache version
caches.keys().then(names => {
  console.log('Caches:', names);
  // Expected: cofind-shell-v6, cofind-static-v6, etc
  // NOT: cofind-v5, cofind-shell-v5
});

// 2. Check devCache entries (auth-related should be NONE)
console.log('devCache entries:');
Object.keys(localStorage)
  .filter(k => k.startsWith('cofind_dev_cache_'))
  .forEach(k => console.log('- ' + k));
// Expected: Mostly empty atau HANYA non-auth URLs

// 3. Check Supabase session stored
const sessionKey = Object.keys(localStorage)
  .find(k => k.includes('auth'));
console.log('Auth key:', sessionKey);
console.log('Session:', localStorage[sessionKey]?.substring(0, 100));
// Expected: Session data exists (JWT token)
```

---

### Step 3: Test Login → Refresh Flow

```javascript
// Open DevTools Console & Network
// 1. Login fresh
// 2. F5 Refresh
// 3. Look for these logs:

[Session Fix] Initializing...          ← Should see this
[Supabase] Valid session found         ← Should see this
[Auth] Valid session found, user: ...  ← Should see this

// If NOT seeing these:
// - sessionFix.js not imported
// - AuthContext not initializing properly
// - Supabase session expired/invalid
```

---

### Step 4: Check Network Requests

In DevTools Network Tab:
```
After F5 refresh, look for:

✅ CORRECT:
GET /                      200  (HTML fresh)
GET /src/index.jsx         304  (static JS OK)
GET https://supabase.co/.. 200  (API fresh)

❌ WRONG:
GET /                      304  (HTML cached - stale session!)
```

**If HTML is 304**:
- Hard refresh: Ctrl+Shift+R
- Clear all site data
- Check if old Service Worker still active

---

### Step 5: Check for Specific Errors

Look in DevTools Console for:

```javascript
// ERROR 1: devCache caching auth URLs
[Dev Cache] HIT (memory): https://supabase.co/rest/v1/profiles
// FIX: Restart server, check devCache.js isAuthRelated()

// ERROR 2: Session expired
[Supabase] Session token has expired
// FIX: Auto-refresh should work, if not check supabase.js

// ERROR 3: Service Worker serving stale page
[Service Worker] Cache First - Serving from cache: /
// FIX: Should say "Network Only" untuk HTML pages

// ERROR 4: Auth context failing
[Auth] Error initializing: ...
// FIX: Check Supabase .env variables

// ERROR 5: bfcache preventing reload
[Session Fix] Page loaded from bfcache
// FIX: Should auto-reload, if not check browser bfcache settings
```

---

## Common Issues & Fixes

### Issue 1: Still Seeing 304 for HTML

**Symptom**:
```
GET /     304 Not Modified
```

**Diagnosis**:
```javascript
// Check browser cache
caches.keys().then(k => console.log(k));
// If result includes v5 or old versions → problem!

// Check SW installed version
navigator.serviceWorker.ready.then(sw => {
  sw.controller?.postMessage({ type: 'GET_VERSION' });
});
```

**Fix**:
1. Hard refresh: **Ctrl+Shift+R**
2. If still 304: Clear all site data manually
   - DevTools → Application → Clear site data
3. Restart dev server
4. Check public/sw.js has `CACHE_VERSION = 'cofind-v6'`

---

### Issue 2: Session Lost After Refresh

**Symptom**:
```
1. Login OK
2. F5 Refresh
3. User undefined, redirect to login
4. Console: [Auth] No active session
```

**Diagnosis**:
```javascript
// 1. Check if session stored in localStorage
const sessionKey = Object.keys(localStorage)
  .find(k => k.includes('sb-'));
console.log('Has session:', !!sessionKey);

// 2. Check session content
console.log(localStorage[sessionKey]?.substring(0, 200));

// 3. Check if devCache preventing profile fetch
Object.keys(localStorage)
  .filter(k => k.includes('profile'))
  .forEach(k => console.log('devCache profile:', k));
```

**Possible Fixes**:

A) **devCache caching profile**
- Clear that specific key: 
  ```javascript
  Object.keys(localStorage)
    .filter(k => k.includes('profile'))
    .forEach(k => localStorage.removeItem(k));
  ```
- Refresh page
- If work → Need to restart server (devCache.js changes)

B) **Session actually expired**
- Check token expiry:
  ```javascript
  import { supabase } from './src/lib/supabase';
  supabase.auth.getSession().then(({ data: { session } }) => {
    const exp = new Date(session.expires_at * 1000);
    console.log('Expires at:', exp);
  });
  ```
- If expired → Try token refresh
  ```javascript
  supabase.auth.refreshSession();
  ```

C) **Supabase not configured**
- Check .env file exists:
  ```powershell
  cat frontend-cofind/.env
  ```
- Must have:
  ```
  VITE_SUPABASE_URL=https://...supabase.co
  VITE_SUPABASE_ANON_KEY=eyJh...
  ```

---

### Issue 3: HMR WebSocket Not Working

**Symptom**:
```
- Changes tidak auto-reload
- Console: HMR error
- WebSocket connection failed
```

**Diagnosis**:
```javascript
// Check if HMR connected
// DevTools → Network → WS filter
// Should see: ws://localhost:5173
// With status: 101 Switching Protocols
```

**Fixes**:
1. Restart dev server:
   ```powershell
   npm run dev  # Stop then start
   ```
2. Check vite.config.js has explicit HMR:
   ```javascript
   hmr: {
     protocol: 'ws',
     host: 'localhost',
     port: 5173,
   }
   ```
3. Try different port (if 5173 already used):
   ```powershell
   npm run dev -- --port 5174
   ```

---

### Issue 4: Service Worker Cache Pollution

**Symptom**:
```
- Multiple old caches in DevTools
- cofind-v1, cofind-v2, cofind-v3, etc
- Page still loading old assets
```

**Diagnosis**:
```javascript
// List all caches
caches.keys().then(names => {
  console.log('All caches:');
  names.forEach(n => console.log('- ' + n));
});
```

**Fix**:
```javascript
// Option 1: Manual delete via DevTools
// Application → Cache Storage → Right-click & delete old caches

// Option 2: Script delete
caches.keys().then(names => {
  Promise.all(
    names
      .filter(n => !n.includes('v6'))  // Keep only v6
      .map(n => caches.delete(n))
  ).then(() => {
    console.log('Deleted old caches');
    location.reload();
  });
});
```

---

### Issue 5: Incognito Mode Works, Normal Mode Doesn't

**Symptom**:
```
- Login works in incognito
- Login fails in normal mode
- But works after hard refresh
```

**Cause**: Browser/SW cache pollution in normal mode, but not in incognito (isolated).

**Fix**:
1. Clear all site data (Application tab)
2. Hard refresh (Ctrl+Shift+R)
3. If still fail: Check if using private localhost settings
4. Try different browser

---

## Advanced Debugging

### Enable Verbose Logging

Add to App.jsx:
```javascript
// Temporary logging
import { supabase } from './lib/supabase';

useEffect(() => {
  // Log every request to Supabase
  supabase.auth.onAuthStateChange((event, session) => {
    console.log('[DEBUG] Auth event:', event, session?.user?.id);
  });
  
  // Log session validation
  import('./lib/supabase').then(({ validateSession }) => {
    validateSession().then(result => {
      console.log('[DEBUG] Session validation:', result);
    });
  });
}, []);
```

### Check Service Worker Requests

In SW (public/sw.js), add detailed logging:
```javascript
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  console.log('[SW-FETCH]', event.request.method, url.pathname, event.request.cache);
  // ... rest of handler
});
```

Then check DevTools:
1. Application → Service Workers → "Inspet"
2. Check console logs dari SW

---

## Recovery Steps (Nuclear Option)

Jika semua gagal:

```powershell
# 1. Kill dev server
Ctrl+C

# 2. Delete cache directories
rm -r frontend-cofind/node_modules
rm -r frontend-cofind/.vite  (Windows: del /s frontend-cofind\.vite)

# 3. Clear npm cache
npm cache clean --force

# 4. Reinstall
npm install

# 5. Start fresh
npm run dev
```

Then in browser:
1. DevTools → Application → Clear all site data
2. Hard refresh (Ctrl+Shift+R)
3. Close DevTools
4. Try login again

---

## Verification Checklist

After applying fixes, verify:

- [ ] vite.config.js has explicit HMR config
- [ ] devCache.js isAuthRelated() extended (20+ patterns)
- [ ] public/sw.js CACHE_VERSION = 'cofind-v6'
- [ ] public/sw.js has networkOnlyStrategyForHTML
- [ ] src/utils/sessionFix.js exists
- [ ] src/App.jsx imports & calls initializeSessionFix()
- [ ] Dev server restarted (npm run dev)
- [ ] Browser cache cleared (Application → Clear site data)
- [ ] Hard refresh (Ctrl+Shift+R)
- [ ] HTML request is 200 (not 304)
- [ ] [Session Fix] logs in console
- [ ] [Supabase] logs show "Valid session found"
- [ ] F5 refresh preserves session
- [ ] No auth errors in console

---

## Still Not Working?

1. **Check logs file**: Review console EXACT error messages
2. **Isolate issue**:
   - Is it vite/HMR? → Try different port
   - Is it SW cache? → Delete manually
   - Is it auth? → Check Supabase .env
   - Is it devCache? → Check if using localStorage
3. **Try minimal test**:
   - Go to localhost:5173 in incognito
   - Try to login
   - Does it work in incognito?
   - If yes → Cache issue, need cleanup
   - If no → Supabase/auth issue
4. **Check docs**:
   - `SESSION_PERSISTENCE_FIX_GUIDE.md` - full explanation
   - `COMPLETE_FIX_SUMMARY.md` - what changed & why
   - `APPLY_SESSION_FIX_CHECKLIST.md` - step-by-step

---

Good luck! 🚀
