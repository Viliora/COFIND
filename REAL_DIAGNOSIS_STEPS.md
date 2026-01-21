# SESSION PERSISTENCE - REAL DIAGNOSIS GUIDE (No Assumptions)

## PENTING: Jangan apply fix apapun dulu!

Kita perlu **identify exact problem terlebih dahulu**. Setiap masalah punya root cause berbeda, dan solusi generic bisa bikin lebih buruk.

---

## STEP 1: RUN DIAGNOSTICS

### Step 1A: Start Fresh
```powershell
# Terminal 1: Kill all servers
Ctrl+C  # Stop dev server jika running

# Terminal 2: Open browser & DevTools
F12  # Open DevTools
Ctrl+Shift+R  # Hard refresh
```

### Step 1B: Navigate to Login
1. Go to http://localhost:5173
2. Open **DevTools → Console tab**
3. Look for log messages:
   - `[Session Fix]` messages
   - `[Supabase]` messages
   - `[Auth]` messages
   - Any **ERROR** or **WARNING**

Copy-paste SEMUA log messages (akan digunakan nanti untuk diagnosis).

### Step 1C: Run Full Diagnostics
Di DevTools Console, paste ini:
```javascript
window.DEBUG_COFIND.fullDiagnostics()
```

**Expected output**: Detailed report tentang:
- ✅ Supabase client status
- ✅ LocalStorage content
- ✅ Service Worker cache
- ✅ Auth context
- ✅ Session simulation

**Screenshot FULL output** (atau copy ke text file).

---

## STEP 2: LOGIN TEST

### Step 2A: Clear Everything
```javascript
// Di Console, run:
localStorage.clear();
sessionStorage.clear();
```

Then hard refresh: **Ctrl+Shift+R**

### Step 2B: Login dengan Test Account
1. Click "Login" button
2. Enter username/password
3. **Watch console & network tab REAL-TIME**

**Expected flow**:
```
Console:
[Auth] Initializing auth...
[Auth] Valid session found, user: uuid-xxx
[Auth] Profile fetched

Network:
POST https://cpnz...supabase.co/auth/v1/token  [200]
GET  https://cpnz...supabase.co/rest/v1/profiles [200]
```

**RECORD**: 
- Apakah login berhasil?
- Error messages?
- Network requests status?

---

## STEP 3: REFRESH TEST (CRITICAL)

### Step 3A: Simple Refresh (F5)
After login berhasil:
1. Press **F5** (simple refresh, bukan hard refresh)
2. **Watch console REAL-TIME**
3. Wait 3-5 seconds sampai page selesai load

**RECORD**: Console output:
```
[Session Fix] Initializing...           ← Should see this
[Supabase] Valid session found          ← Should see this or ERROR?
[Auth] Profile fetched                  ← Should see this
```

### Step 3B: Check Network Tab
Look at Network tab untuk requests yang paling AWAL:

```
Expected:
✅ Document (/)              200
✅ supabase auth session     200
✅ profile fetch             200

❌ Problem signs:
❌ 401 Unauthorized
❌ 403 Forbidden
❌ Network errors
```

### Step 3C: Observe UI
```
Expected:
✅ User still logged in
✅ Profile visible
✅ No "loading" spinner forever

❌ Problem:
❌ Redirect to login
❌ "Loading..." forever
❌ Blank screen
```

---

## STEP 4: IDENTIFY ROOT CAUSE

Based on Step 1-3 results, which scenario matches YOUR situation?

### SCENARIO A: Login Works, BUT F5 Redirect to Login

**This means**: Session not persisting after refresh.

```
DIAGNOSIS CHECKLIST:
□ Is localStorage still empty after F5?
  - If YES → Session not saved to localStorage
  - If NO → Session saved but not being read

□ Do you see "[Auth] No active session" in console?
  - If YES → validateSession() returning false
  - Check: Is Supabase client initialized?

□ Do you see "[Supabase] Session validation error" in console?
  - If YES → Supabase client returning error
  - Check: Are .env variables correct?
  - Check: Is Supabase project accessible?

□ In Network tab, does auth request fail (401/403)?
  - If YES → Supabase rejecting session
  - Check: Token expired?
  - Check: Token stored incorrectly?
```

**SPECIFIC FIX for Scenario A**: See section FIXES below.

### SCENARIO B: Login Doesn't Work (401/403 error)

**This means**: Supabase authentication itself failing.

```
DIAGNOSIS:
□ Is VITE_SUPABASE_URL correct?
  - Check: frontend-cofind/.env file
  - Should be: https://cpnzglvpqyugtacodwtr.supabase.co
  
□ Is VITE_SUPABASE_ANON_KEY correct?
  - Check: frontend-cofind/.env file
  - Should start with: eyJhbGc...
  
□ Can you access Supabase dashboard?
  - Go to: https://supabase.com
  - Login, check project "COFIND"
  - Check: Auth enabled?
  - Check: JWT Secret configured?

□ In Network tab, check Supabase response:
  - Click failed request
  - Go to "Response" tab
  - What's the error message?
```

**SPECIFIC FIX for Scenario B**: Check Supabase configuration.

### SCENARIO C: Page Loads Blank or Infinite Loading

**This means**: React component stuck in loading state.

```
DIAGNOSIS:
□ In Console, see any JavaScript errors?
  - Red error messages?
  - Look for stack trace

□ Is AuthContext initializing?
  - Should see "[Auth] Initializing auth..."
  - If not → AuthContext not rendering

□ Is sessionFix.js running?
  - Should see "[Session Fix] Initializing..."
  - If not → sessionFix.js not imported
```

**SPECIFIC FIX for Scenario C**: Check AuthContext mounting.

---

## STEP 5: CHECK CRITICAL CONFIGURATION

### Check 1: .env File
```powershell
cd frontend-cofind
cat .env
```

**Must have**:
```
VITE_API_BASE=http://localhost:5000
VITE_SUPABASE_URL=https://cpnzglvpqyugtacodwtr.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGc...
```

**If missing**: Create it!

### Check 2: Supabase Connection
```javascript
// Di DevTools Console:
import { supabase, isSupabaseConfigured } from './src/lib/supabase';

console.log('Configured:', isSupabaseConfigured);
console.log('Client:', !!supabase);

// Try to get session manually
supabase.auth.getSession().then(({ data, error }) => {
  console.log('Session:', data?.session);
  console.log('Error:', error);
});
```

### Check 3: AuthContext Integration
```javascript
// Is AuthContext wrapping app?
// Check src/App.jsx - should have:
// <AuthProvider>
//   <AppContent />
// </AuthProvider>
```

---

## STEP 6: COLLECT EXACT ERROR MESSAGES

**Copy-paste ke somewhere safe**:

### When you see errors:
1. **Right-click console error**
2. **Copy → Copy as JSON**
3. **Paste into text file**

### Example error info needed:
```
TIMESTAMP: 2026-01-15 14:23:45
SCENARIO: F5 refresh after login
BROWSER: Chrome 143 (or Firefox, Safari, etc)
DEVICE: Desktop/Mobile

CONSOLE ERRORS:
[exact error message]

NETWORK ERRORS:
[failing request URL, status code, response]

LOCALSTORAGE STATE:
[keys present/absent]

EXPECTED BEHAVIOR:
[what should happen]

ACTUAL BEHAVIOR:
[what actually happens]
```

---

## FIXES (Based on Diagnosis)

### FIX A: Session Not Persisting (Scenario A)

If issue is "login works, but F5 loses session":

**Root cause likely**:
- localStorage not saving session
- Session reading code broken
- Supabase client not initialized early enough

**Solution**:
```jsx
// Check src/lib/supabase.js initialization
// Should have: persistSession: true, storage: localStorage

// Check AuthContext useEffect dependencies
// Should call validateSession() on mount

// Verify no code deletes localStorage on page load
// Check: devCache.js clearAuthRelatedCache()
```

### FIX B: Login Failed (Scenario B)

If issue is "login button doesn't work":

**Root cause likely**:
- Supabase not configured
- Wrong credentials
- Supabase project issue

**Solution**:
1. Verify .env correct
2. Login to supabase.com dashboard
3. Check Auth settings
4. Try manual Supabase test:
```javascript
import { createClient } from '@supabase/supabase-js';
const client = createClient(url, key);
client.auth.signInWithPassword({ email: 'test@cofind.app', password: 'test' });
```

### FIX C: Infinite Loading (Scenario C)

If issue is "page stuck loading":

**Root cause likely**:
- AuthContext initialization hanging
- Supabase client promise never resolves
- Component not handling loading state

**Solution**:
```jsx
// Add timeout to AuthContext initialization
// Add error boundary to catch exceptions
// Check if Supabase API responding
```

---

## NEXT STEPS

1. **RUN Step 1-5 above** (don't skip!)
2. **IDENTIFY which scenario matches**
3. **Collect error messages**
4. **Report results** with:
   - Exact console errors
   - Network tab screenshots
   - Step-by-step what happened
   - What you expected vs actual
5. **THEN apply specific fix**

---

## DO NOT:

❌ Apply random fixes from StackOverflow  
❌ Delete code without understanding  
❌ Assume issue is caching (might not be!)  
❌ Clear browser data without documenting state first  
❌ Change multiple things at once  

---

## DO:

✅ Document exact behavior  
✅ Check console & network tab REAL-TIME  
✅ Collect error messages VERBATIM  
✅ Test one scenario at a time  
✅ Keep backup of working code  

---

## PROFESSIONAL APPROACH

This is how professional developers debug:
1. **Reproduce** - Can you repeat the issue?
2. **Document** - What exact steps? What errors?
3. **Isolate** - Is it auth? Cache? Network? React?
4. **Test** - Try minimal case to confirm root cause
5. **Fix** - Apply targeted fix based on root cause
6. **Verify** - Test fix doesn't break something else

**You have all the tools now. This is not skill issue, this is methodical debugging. You got this! 💪**
