# 🧪 Quick Testing Guide - Session Fix

## Prerequisites
- Browser DevTools open (F12)
- Console tab visible for logs
- Network tab for monitoring API calls

---

## Test 1: Logout Completeness ⏱️ ~2 min

### Steps:
1. **Login** with your test account
   - Username: `testuser`
   - Check: User dropdown shows your username (not "@user")

2. **Click Logout** from Navbar
   - Watch console for: `[Auth] ✅ Sign out complete`
   - Watch console for: `[Supabase] Cleared localStorage key: sb-xxxxx`

3. **Open DevTools → Application → Local Storage**
   - Click the app domain
   - Check: NO keys starting with `sb-` exist
   - Check: NO keys with `supabase` in name

4. **Refresh Browser**
   - Expected: Auto-redirect to login page
   - NOT logged in

### ✅ Pass If:
- Console shows complete logout logs
- No "sb-" keys in LocalStorage
- Page is at `/login` after refresh
- Profile shows anonymous state

---

## Test 2: Close & Reopen (Force Kill) ⏱️ ~3 min

### Steps:
1. **Login** with test account
2. **Completely close browser** (use Alt+F4 or Force Kill)
3. **Reopen browser** immediately
4. **Navigate to app URL**
   - Expected: Auto-redirect to `/login`
   - NOT showing logged-in state

5. **Open DevTools → Application → Local Storage**
   - Check: NO session tokens exist

### ✅ Pass If:
- App requires fresh login
- No session restoration
- Profile shows anonymous state

---

## Test 3: Profile Data Accuracy ⏱️ ~2 min

### Steps:
1. **Login** with username: `testuser`

2. **Go to Profile Page** (/profile)
   - Expected: Shows username as `testuser`
   - NOT showing `@user` or just `user`

3. **Check Full Name**
   - Expected: Shows correct full name
   - NOT empty or broken

4. **Logout & Login Again**
   - Go to profile again
   - Expected: Same correct data

### ✅ Pass If:
- Username displays correctly
- Full name displays correctly
- Profile data persists after logout/login cycle

### 🔴 Fail If:
- Shows `@user` or `user` (broken parsing)
- Shows empty username
- Profile misses data after reload

---

## Test 4: Coffee Shop Data Fetching ⏱️ ~3 min

### Steps:
1. **Login**

2. **Go to any Coffee Shop Detail page**
   - Click on any shop card
   - Expected: Reviews load
   - Expected: Shop details show

3. **Open DevTools → Network tab**
   - Filter: `supabase`
   - Look for: `/rest/v1/reviews` requests
   - Expected: Status `200` (green)
   - NOT `401` (auth error)
   - NOT `403` (forbidden)

4. **Check Console**
   - Expected: `[ReviewList] ✅ Loaded X reviews from Supabase`
   - NOT: Any `Unauthorized` errors

### ✅ Pass If:
- Reviews load successfully
- Network status is 200
- No auth errors in console

### 🔴 Fail If:
- Network shows 401/403
- Reviews don't load
- Console shows "Unauthorized"

---

## Test 5: Logout & Immediate Login ⏱️ ~2 min

### Steps:
1. **Login** with test account
2. **Click Logout**
3. **IMMEDIATELY click Login** (within 2 seconds)
4. **Fill login form**
   - Username: `testuser`
   - Password: `password123`
5. **Click Login button**
   - Expected: "Login berhasil! Mengarahkan..."
   - Expected: Redirects to home page
   - NOT stuck on login page

### ✅ Pass If:
- Login succeeds
- Redirects to home
- Can immediately use app

### 🔴 Fail If:
- Shows error
- Stuck on login page
- Can't access dashboard

---

## Test 6: Token Expiry Detection ⏱️ ~4 min

### Steps:
1. **Login** (generates 1-hour token)

2. **Open DevTools → Console**
   - Look for: `[Supabase] Valid session found`

3. **Open DevTools → Application → Local Storage**
   - Find: `sb-xxx` key with auth session
   - Right-click → Edit
   - Manually reduce `expires_at` to current time (to simulate expiry)
   - Example: Change `expires_at: 1704844800` to `1704844500`

4. **Refresh Browser**
   - Expected: Console shows validation check
   - Expected: Page redirects to login OR auto-refreshes token

### ✅ Pass If:
- App detects expired token
- Either: Auto-refresh works OR login required
- No silent failures

---

## Test 7: Tab Visibility Change ⏱️ ~3 min

### Steps:
1. **Login**

2. **Open 2 browser windows** (same app, same domain)
   - Window A: Logged in
   - Window B: Logged in

3. **In Window A: Logout**

4. **Switch to Window B** (click on tab/window to focus)
   - Expected: Console shows `[Auth] Tab became visible, validating session...`
   - Expected: Detects logout
   - App behavior depends on implementation

### ✅ Pass If:
- Logout in one window detected
- Visibility handler runs
- Session validated properly

---

## Console Output Checklist

### Expected Good Logs:
```
[Auth] Initializing auth, validating session...
[Supabase] Valid session found, user: abc-123
[Auth] ✅ Cleared React state
[Auth] ✅ Cleared Supabase session
[Auth] ✅ Cleared sessionStorage
[ReviewList] ✅ Loaded 5 reviews from Supabase
```

### Expected Bad Logs (should NOT see):
```
❌ Unauthorized
❌ Cannot read property of undefined
❌ [Token refresh failed]
❌ 401 Unauthorized
❌ 403 Forbidden
```

---

## Quick Reference: What Changed

| Scenario | Before | After |
|----------|--------|-------|
| Close without logout | Stale session persists | Fresh login required |
| Token expires | Silent failures | Auto-detect & refresh |
| Logout → Login cycle | Stuck on login page | Smooth redirect |
| Profile after logout | `@user` broken | Correct username |
| Data fetch | 401 errors | Works with valid token |

---

## Debugging Tips

### If Test Fails:

1. **Check Console for Errors**
   - Open F12 → Console
   - Look for red errors
   - Read full error message

2. **Check Storage**
   - Application → Local Storage
   - Look for unexpected `sb-` keys
   - Look for old `cofind_*` keys

3. **Check Network**
   - Network tab → filter "supabase"
   - Look at response status
   - 401 = auth problem
   - 403 = permission problem

4. **Check Auth State**
   - Application → Local Storage → search "SUPABASE"
   - Look at session token structure
   - Check if `expires_at` is in future

---

## Report Issues

If tests fail, check:

```
In Console, look for:
1. [Auth] logs with error messages
2. [Supabase] validation results
3. Full stack trace of any errors

Then share:
- Console error screenshot
- Network tab with failed request
- Steps that failed
- Browser version
```

---

**Status:** Ready to test ✅  
**Time to complete all tests:** ~20 minutes  
**Expected result:** All tests pass ✅
