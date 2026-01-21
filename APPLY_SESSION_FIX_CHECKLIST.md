# QUICK APPLY CHECKLIST

## Step 1: Restart Dev Server (IMPORTANT!)
```powershell
# Terminal 1: Kill old server
Ctrl+C

# Terminal 2: Clear npm cache
npm cache clean --force

# Terminal 3: Reinstall dependencies (optional)
npm install

# Terminal 4: Start fresh dev server
npm run dev
```

**Why**: HMR config changes di vite.config.js memerlukan server restart.

---

## Step 2: Clear All Caches

### Browser Cache
1. Open DevTools (F12)
2. Go to: **Application** tab
3. Click **Clear site data** button (bottom-left)
4. Check all: Cookies, Site data, Cached images, etc.
5. Click **Clear**

### Service Worker
```javascript
// Run di DevTools Console:
caches.keys().then(names => {
  Promise.all(names.map(name => caches.delete(name)))
    .then(() => console.log('All caches deleted'))
});

// Unregister SW
navigator.serviceWorker.getRegistrations()
  .then(regs => Promise.all(regs.map(r => r.unregister())));
```

### Hard Refresh
```
Ctrl+Shift+R  (Windows/Linux)
Cmd+Shift+R   (Mac)
```

---

## Step 3: Test Fresh Login

1. Open http://localhost:5173
2. Should go to home page (not logged in)
3. Click **Login** button
4. Enter test credentials
5. Should see redirect to home + user profile appears

### Expected Behavior:
- No 401 errors
- No session errors
- User object di console: `[Auth] Valid session found, user: ...`

---

## Step 4: Test Session Persistence (CRITICAL)

1. You're logged in
2. **Press F5** (simple refresh, tidak hard refresh)
3. **Expected**: 
   - ✅ Page reloads
   - ✅ User still logged in
   - ✅ Profile visible
   - ✅ No "logging in" spinner
   - ✅ Network tab shows HTML as **200** (not 304)

### Check Console:
```
[Session Fix] Initializing session persistence fixes...
[Supabase] Valid session found, user: uuid-xxx
[Session Fix] Initialization complete
```

### Check Network Tab:
1. Open DevTools → Network
2. Refresh (F5)
3. Click on the "/" (root HTML) request
4. Check **Status**: Should be **200**, NOT **304**
5. If 304: Press Ctrl+Shift+R dan ulangi

---

## Step 5: Test 304 Fix

### Before (stale):
- Many 304 Not Modified responses
- HTML loaded from cache

### After (fixed):
```
GET /          200  (HTML page, always fresh)
GET /src/...   304  (Static JS/CSS, OK to cache)
```

---

## Step 6: Verify Fixes Applied

### 1. Check vite.config.js
```bash
grep -n "hmr:" frontend-cofind/vite.config.js
# Should show explicit config dengan protocol, host, port
```

### 2. Check devCache.js
```bash
grep -n "isAuthRelated" frontend-cofind/src/utils/devCache.js
# Should show expanded function dengan 20+ patterns
```

### 3. Check Service Worker
```bash
grep -n "CACHE_VERSION = 'cofind-v6'" frontend-cofind/public/sw.js
# Should show v6, not v5
```

### 4. Check sessionFix.js exists
```bash
ls frontend-cofind/src/utils/sessionFix.js
# Should exist
```

### 5. Check App.jsx integration
```bash
grep -n "initializeSessionFix" frontend-cofind/src/App.jsx
# Should import dan call di useEffect
```

---

## Step 7: Monitor Logs

Open DevTools → Console, filter by:
- `[Session Fix]` → Session fix initialization logs
- `[Supabase]` → Supabase session validation logs
- `[Dev Cache]` → Cache operations (should show SKIP CACHE for auth URLs)

---

## Troubleshooting

### Problem: Still getting 304 responses
**Solution**: 
1. Hard refresh: Ctrl+Shift+R
2. Clear all browser cache (Application tab)
3. Check if old Service Worker active: Unregister via DevTools

### Problem: Session still lost after refresh
**Solution**:
1. Check console untuk error messages
2. Verify Supabase .env variables
3. Check if using localStorage (not sessionStorage)
4. Try incognito/private mode (no cache)

### Problem: HMR not working (changes not auto-reload)
**Solution**:
1. Restart npm dev server
2. Check console untuk HMR error
3. Verify vite.config.js syntax (correct indentation, etc)

### Problem: Can't login
**Solution**:
1. Check Supabase configured (.env variables set)
2. Check browser console untuk auth errors
3. Hard refresh page
4. Try incognito mode (isolate cache issues)

---

## What Each Fix Does

| Fix | Problem Solved | How |
|-----|----------------|-----|
| vite.config.js HMR | WebSocket ambiguity | Explicit protocol, host, port |
| devCache.js extended | Auth URLs being cached | Extended isAuthRelated() patterns |
| Service Worker v6 | HTML cached (stale session) | Network-only for HTML pages |
| SW cache-busting headers | 304 Not Modified responses | Add cache-busting headers, query param |
| sessionFix.js init | Multiple session issues | Clear old caches, detect bfcache |
| supabase.js no-cache | API responses cached | Add Cache-Control headers to client |

---

## Expected Final State

After all fixes applied and tested:

```
✅ Login works
✅ Session persists after F5 refresh
✅ No 304 responses for HTML
✅ No "session invalid" errors
✅ Dev experience smooth (HMR working)
✅ Mobile & incognito mode work
✅ Back-forward navigation correct
✅ Hard refresh works (clears everything)
```

---

## Files Modified (Summary)

1. ✅ `frontend-cofind/vite.config.js` - HMR config
2. ✅ `frontend-cofind/src/utils/devCache.js` - Auth detection
3. ✅ `frontend-cofind/public/sw.js` - Cache strategy
4. ✅ `frontend-cofind/src/lib/supabase.js` - Session handling
5. ✅ `frontend-cofind/src/App.jsx` - sessionFix integration
6. ✅ `frontend-cofind/src/utils/sessionFix.js` - NEW utility
7. ✅ Root: `SESSION_PERSISTENCE_FIX_GUIDE.md` - Full documentation

---

## Need Help?

If issues persist:
1. Check `SESSION_PERSISTENCE_FIX_GUIDE.md` Troubleshooting section
2. Review `[Session Fix]` logs di console
3. Check Network tab untuk exact failures
4. Try on different browser
5. Try incognito/private mode

Good luck! 🚀
