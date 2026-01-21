## 🚀 Session Recovery Testing Guide

### Current System Status
✅ Backend: http://localhost:5000 (SQLite local database)  
✅ Frontend: http://localhost:5173 (Vite dev server)  
✅ Coffee shop data: Loads from local database (instant, no timeout)  
✅ Session recovery: Now improved with getUser() fallback

### Test Procedure

#### Step 1: Open Browser
- Open http://localhost:5173 in Chrome/Firefox
- You should see COFIND homepage with coffee shops

#### Step 2: Login
- Click "Masuk" (Login) button
- Enter test credentials
- After successful login:
  - You should see "Selamat Datang, [username]"
  - 15 coffee shops should be visible on homepage
  - Check console (F12) for logs

#### Step 3: Refresh Page (F5)
- Press **F5** to hard refresh
- Wait for page to reload completely
- **EXPECTED RESULT**:
  - Session should persist ✅
  - Username still shows ✅
  - Coffee shops still loaded ✅

#### Step 4: Check Console Logs (F12 → Console tab)
Look for these logs (in order):

```
[Auth] Initializing auth, validating session...
[Auth] Checking localStorage for session token...
[Supabase] getSession result: { hasSession: true, userId: "xxx", error: null }
[Auth] Session validation result: { valid: true, userId: "xxx", error: null }
[Auth] ✅ Valid session found, user: xxx
[Auth] Fetching profile for userId: xxx
[Auth] Profile found: [your_username]
[ShopList] Loading coffee shops from backend API...
[ShopList] ✅ Loaded from backend: 15 shops
```

### Expected Behavior After Fix

| Action | Before | After |
|--------|--------|-------|
| Login | Works | ✅ Works |
| F5 Refresh | Session lost ❌ | Session persists ✅ |
| Username after refresh | Shows "Login" | Shows username ✅ |
| Coffee shops after refresh | Infinite loading ❌ | Loads instantly ✅ |
| Token expiry | Crashes | Auto-refreshes ✅ |

### Troubleshooting

**Problem:** Session still lost after F5
- Clear browser cache (Ctrl+Shift+Delete)
- Check localStorage (F12 → Application → LocalStorage)
- Should see key `sb-{project-id}-auth-token` with session data

**Problem:** "Supabase tidak dikonfigurasi" error
- Check .env file has VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
- These should match your Supabase project settings

**Problem:** Coffee shops not loading
- Check backend is running: `curl http://localhost:5000/api/coffeeshops`
- Should return 15 shops instantly

### What Was Fixed

1. **Added `getUser()` fallback** in `validateSession()`
   - `getSession()` checks memory/localStorage
   - `getUser()` queries Supabase to recover session
   - Falls back if either fails

2. **Improved session recovery logging**
   - More detailed console logs
   - Can now debug session issues easily

3. **Ensured Supabase config**
   - `persistSession: true` - saves to localStorage
   - `autoRefreshToken: true` - auto-refreshes expired tokens
   - `detectSessionInUrl: true` - detects session in URL after redirect

### Next Steps (If Still Not Working)

1. Check browser DevTools Network tab
   - See if API calls are succeeding
   - Check response status codes

2. Check localStorage
   - Open F12 → Application → LocalStorage → localhost:5173
   - Look for `sb-{projectId}-auth-token` key
   - Should have valid JSON with access_token

3. Check Supabase Dashboard
   - Verify user exists and is not suspended
   - Check auth logs for any errors

---

**Date:** January 18, 2026  
**Migration Status:** Supabase → SQLite Complete ✅  
**Session Recovery:** Implemented & Ready for Testing ✅
