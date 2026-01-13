# Session Fix - Visual Flow Diagrams

## 🔄 Close Without Logout Scenario

### BEFORE (Broken) ❌
```
User in App
    ↓
🔴 Close Browser (no logout)
    ↓
Session token stays in localStorage
    ↓
App reopens
    ↓
Auth auto-restores token (OLD FLOW)
    ↓
❌ TOKEN IS EXPIRED but not validated!
    ↓
React state: isAuthenticated = true
    ↓
API call: supabase.from('reviews').select()
    ↓
❌ Supabase returns 401 UNAUTHORIZED
    ↓
Silent failure - user sees empty data
    ↓
❌ Stuck in broken state
    - Can't fetch data
    - Can't logout properly
    - Can't login fresh
```

### AFTER (Fixed) ✅
```
User in App
    ↓
🟢 Close Browser (no logout)
    ↓
Session token stays in localStorage
    ↓
App reopens
    ↓
Auth initializes → calls validateSession()
    ↓
✅ TOKEN IS VALIDATED
    - Checks expiry time
    - Token expired? → clearSupabaseSession()
    - Token expiring? → auto-refresh
    ↓
React state: isAuthenticated = false (because token invalid)
    ↓
User redirected to login page
    ↓
✅ Fresh login required
    ↓
Full working session established
    - Can fetch all data
    - Can logout cleanly
    - Can use all features
```

---

## 🚪 Logout Flow

### BEFORE (Incomplete) ❌
```
User clicks Logout
    ↓
signOut()
  ├─ Sign out from Supabase
  └─ Remove some localStorage keys
    ↓
❌ Some tokens might remain:
  - sb-access-token still there
  - sb-refresh-token still there
  - Old cache entries
    ↓
User tries to login
    ↓
❌ Stale tokens cause conflicts
    ↓
Login stuck or behaves oddly
```

### AFTER (Complete) ✅
```
User clicks Logout
    ↓
signOut() - 5-STEP NUCLEAR CLEANUP:
  ├─ Step 1: Clear React state
  │          (user = null, profile = null)
  │
  ├─ Step 2: Sign out from Supabase
  │          (server-side cleanup)
  │
  ├─ Step 3: Remove ALL localStorage keys
  │          (sb-*, supabase*, cofind_*, cache_*)
  │
  ├─ Step 4: Clear sessionStorage
  │          (all session data)
  │
  └─ Step 5: Delete IndexedDB databases
             (cached data)
    ↓
✅ ZERO TRACE LEFT
    ↓
User logged out completely
    ↓
Redirected to login page
    ↓
✅ Fresh login available
```

---

## 🔐 Token Validation Flow

### validateSession() Function
```
validateSession() called
    ↓
Does session exist in localStorage?
  ├─ NO  → return { valid: false }
  └─ YES → Continue
    ↓
Get session from Supabase
    ├─ Error? → return { valid: false, error }
    └─ Success? → Continue
    ↓
Check token expiry:
  current_time = now()
  expires_at = session.expires_at (from token)
  time_until_expiry = expires_at - current_time
    ↓
Is token already expired?
  ├─ YES (time_until_expiry < 0)
  │  → return { valid: false, error: 'Token expired' }
  └─ NO → Continue
    ↓
Is token expiring soon?
  ├─ YES (time_until_expiry < 5 minutes)
  │  → Auto-refresh token
  │  └─ Successful? → return { valid: true, session: refreshed }
  │                 → Failed? → return { valid: false }
  └─ NO → Continue
    ↓
✅ Token is valid
    return { valid: true, user: session.user, session }
```

---

## 🔄 Login Flow (After Fix)

```
User at login page
    ↓
Enters username + password
    ↓
Clicks Login button
    ↓
signIn() function
  └─ Calls Supabase auth
    ↓
Supabase validates credentials
  ├─ Invalid → return error
  └─ Valid   → return session + token
    ↓
Auth context receives session
    ↓
onAuthStateChange listener triggers
  (from Supabase)
    ↓
handleAuthEvent() processes event
  ├─ Load profile data
  └─ Migrate favorites
    ↓
useEffect detects isAuthenticated changed
    ↓
✅ Redirect to home page
    ↓
User in authenticated state
    ↓
All API calls work with valid token
```

---

## 📱 Tab Visibility Change

### User Switches Tab
```
App was in background (invisible)
    ↓
User clicks tab to bring it to foreground
    ↓
document.visibilitychange event fires
    ↓
onVisibility() handler runs
    ↓
is_visible?
  ├─ NO  → Do nothing, return
  └─ YES → Continue
    ↓
validateSession() checks current token
    ↓
Token still valid?
  ├─ YES → Refresh profile data
  │      └─ Update React state
  │
  └─ NO  → Token invalid/expired
         ├─ clearSupabaseSession()
         └─ Clear React state
    ↓
App now has fresh session state
```

---

## 📊 State Machine

### Before (Broken) ❌

```
             Login
               ↓
        ┌──────────────┐
        │ LOGGED_IN    │
        │ (might stale)│
        └──────────────┘
              ↓ Logout
        ┌──────────────┐
        │ LOGGED_OUT   │
        │ (partial     │
        │  cleanup)    │
        └──────────────┘
              ↓ Login Again
        ┌──────────────┐
        │ LOGGED_IN    │
        │ (confused    │
        │  state)      │
        └──────────────┘

❌ Unstable transitions
❌ Stuck states possible
❌ Silent failures
```

### After (Fixed) ✅

```
          ┌─────────────────┐
          │   LOGGED_OUT    │
          │ (Clean state)   │
          └─────────────────┘
                ↓ Login
          ┌─────────────────┐
          │   VALIDATING    │
          │ (Token check)   │
          └─────────────────┘
                ↓ Valid?
          ┌─────────────────┐
          │   LOGGED_IN     │
          │ (Fresh session) │
          └─────────────────┘
                ↓ Logout
          ┌─────────────────┐
          │   CLEANUP       │
          │ (5-step purge)  │
          └─────────────────┘
                ↓
          ┌─────────────────┐
          │   LOGGED_OUT    │
          │ (Zero trace)    │
          └─────────────────┘

✅ Clear transitions
✅ No stuck states
✅ Explicit error handling
```

---

## 🎯 Data Flow

### API Call After Login (With Validation)

```
ReviewList component
    ↓
useEffect runs
    ↓
fetchReviews() called
    ↓
Step 1: Validate session
  validateSession()
    ├─ Token valid? ✅
    │  └─ Continue to API call
    │
    └─ Token invalid? ❌
       └─ Log warning, continue anyway
          (for public data)
    ↓
Step 2: Call Supabase API
  supabase.from('reviews').select()
    ↓
Step 3: Handle response
  ├─ Success: setReviews(data)
  ├─ 401 Error: Log "Unauthorized"
  └─ Other Error: setError(msg)
    ↓
Step 4: Display result
  ├─ Review list loads
  ├─ Error message shows
  └─ Empty state if no reviews
```

---

## 🔍 Console Log Flow

### Successful Login
```
[Auth] Initializing auth, validating session...
[Supabase] No active session
[Auth] Initializing auth, validating session...
[Auth] User clicks Login
[Auth] Sign in successful
[Auth] Valid session found, user: user-123-abc
[Auth] Fetching profile for userId: user-123-abc
[Auth] Profile data: { username: "testuser", ... }
[ReviewList] ✅ Loaded 5 reviews from Supabase
```

### Logout Flow
```
[Navbar] Logging out - force clearing all storage...
[Auth] Starting comprehensive sign out...
[Auth] ✅ Cleared React state
[Auth] Clearing Supabase session...
[Supabase] Cleared localStorage key: sb-abc123
[Auth] ✅ Cleared Supabase session
[Auth] ✅ Cleared 15 localStorage keys
[Auth] ✅ Cleared sessionStorage
[Auth] ✅ Cleared IndexedDB
[Auth] ✅ Sign out complete
[Navbar] ✅ All storage cleared, navigating to login...
```

### Close & Reopen (Detecting Stale Session)
```
[Auth] Initializing auth, validating session...
[Supabase] Session validation error: Token expired
[Auth] No valid session found: Token expired
[Auth] Clearing stale session
[Supabase] Cleared localStorage key: sb-expired123
[Auth] ✅ Sign out complete
→ User redirected to login page
```

---

## 📈 Success Metrics

### ✅ Metric 1: Clean Logout
```
Before logout:   15 localStorage keys with "sb-"
Logout
After logout:    0 localStorage keys with "sb-"
                 → Success! ✅
```

### ✅ Metric 2: Session Validation
```
Token expiry:   1704844800
Current time:   1704844700
Time to expiry: 100 seconds (> 5 min)
Result:         Valid ✅

Token expiry:   1704844700
Current time:   1704844700  
Time to expiry: 0 seconds (= expired)
Result:         Invalid ❌
```

### ✅ Metric 3: Login After Logout
```
[Auth] Sign out complete → 0ms
Login form appears → 0ms
User submits form → 100ms
[Auth] Valid session found → 200ms
Redirect to home → 300ms
Total time: < 1 second ✅
```

---

**All diagrams represent the fixed behavior** ✅
