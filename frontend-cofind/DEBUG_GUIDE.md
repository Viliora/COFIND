# 🔧 Debug Guide untuk Auth Session & Supabase Issues

## 🚀 Quick Start

Buka browser console dan gunakan tools berikut:

### 1. **Check Auth State**
```javascript
// Check current auth state
window.__cofindAuthDebug.checkState()

// Check storage
window.__cofindAuthDebug.checkStorage()
```

### 2. **Trigger Bugs untuk Testing**
```javascript
// Test auto-login bug
window.__cofindAuthDebug.triggerBug('auto-login')

// Test session restore bug
window.__cofindAuthDebug.triggerBug('session-restore')

// Test timeout
window.__cofindAuthDebug.triggerBug('timeout')

// Test storage conflicts
window.__cofindAuthDebug.triggerBug('storage-conflict')
```

### 3. **Monitor Auth State**
```javascript
// Monitor auth state for 30 seconds
window.__cofindAuthDebug.monitorAuth(30000)
```

### 4. **Test Supabase Connection**
```javascript
// Test connection with retry
window.__cofindAuthDebug.testConnection(3)
```

### 5. **Check Error Log**
```javascript
// Get error log
window.__cofindErrorTracker.getSummary()

// Get all tracked errors
window.__cofindErrorTracker.getErrors()

// Clear error log
window.__cofindErrorTracker.clear()
```

---

## 🐛 Common Issues & How to Debug

### Issue 1: Auto-Login Setelah Logout

**Symptoms:**
- User logout tapi masih auto-login setelah hard reload
- Logout flag ada tapi session masih restore

**Debug Steps:**
```javascript
// 1. Check current state
window.__cofindAuthDebug.checkState()

// 2. Check logout flag
localStorage.getItem('cofind_user_logged_out')

// 3. Check Supabase session
const { data } = await supabase.auth.getSession()
console.log('Session:', data.session)

// 4. Trigger bug test
window.__cofindAuthDebug.triggerBug('auto-login')

// 5. Monitor for 30 seconds
window.__cofindAuthDebug.monitorAuth(30000)
```

**Expected:**
- Logout flag: `'true'`
- Supabase session: `null`
- User state: `null`

**If Bug Detected:**
```javascript
// Emergency clear
window.__cofindAuthDebug.clearAll()
```

---

### Issue 2: Supabase Request Timeout

**Symptoms:**
- Request ke Supabase timeout setelah 30 detik
- Review tidak muncul
- Loading stuck

**Debug Steps:**
```javascript
// 1. Test connection
window.__cofindAuthDebug.testConnection(3)

// 2. Check timeout errors
window.__cofindErrorTracker.getSummary()

// 3. Check recent timeouts
const errors = window.__cofindErrorTracker.getErrors()
console.table(errors.timeouts.slice(-10))
```

**Expected:**
- Connection test: Success dalam < 5 detik
- No timeout errors

**If Timeout Detected:**
```javascript
// Check network
navigator.onLine // Should be true

// Check Supabase status
// Visit: https://status.supabase.com

// Try manual query
const { data, error } = await supabase
  .from('reviews')
  .select('*')
  .limit(1)
console.log('Manual test:', { data, error })
```

---

### Issue 3: Session Restore Issues

**Symptoms:**
- Session tidak restore setelah refresh
- User harus login lagi
- Profile tidak muncul

**Debug Steps:**
```javascript
// 1. Check state before refresh
const beforeState = await window.__cofindAuthDebug.checkState()

// 2. Simulate refresh (hard reload)
// Ctrl+Shift+R or F5

// 3. Check state after refresh
const afterState = await window.__cofindAuthDebug.checkState()

// 4. Compare
console.log('Before:', beforeState)
console.log('After:', afterState)
```

**Expected:**
- Session should persist (if not logged out)
- Profile should restore
- User state should match

---

### Issue 4: Storage Conflicts

**Symptoms:**
- Logout flag set tapi Supabase keys masih ada
- Session exists tapi logout flag is true

**Debug Steps:**
```javascript
// 1. Check for conflicts
window.__cofindAuthDebug.triggerBug('storage-conflict')

// 2. Check storage
window.__cofindAuthDebug.checkStorage()

// 3. Check auth issues
window.__cofindErrorTracker.getSummary()
```

**Expected:**
- No conflicts
- Either logout flag OR Supabase keys (not both)

**If Conflict Detected:**
```javascript
// Clear all and set logout flag
window.__cofindAuthDebug.clearAll(true)
```

---

## 📊 Monitoring & Tracking

### Real-time Monitoring
```javascript
// Monitor auth state for 1 minute
const stopMonitoring = window.__cofindAuthDebug.monitorAuth(60000)

// Stop manually
stopMonitoring()
```

### Error Tracking
```javascript
// Get error summary
const summary = window.__cofindErrorTracker.getSummary()
console.log('Errors:', summary.errors)
console.log('Timeouts:', summary.timeouts)
console.log('Auth Issues:', summary.authIssues)
```

### Export Error Log
```javascript
// Get all errors
const errors = window.__cofindErrorTracker.getErrors()

// Export as JSON
const json = JSON.stringify(errors, null, 2)
console.log(json)

// Copy to clipboard
navigator.clipboard.writeText(json)
```

---

## 🧪 Testing Scenarios

### Test 1: Login → Logout → Hard Reload
```javascript
// 1. Login
// 2. Check state
await window.__cofindAuthDebug.checkState()

// 3. Logout
// 4. Check state
await window.__cofindAuthDebug.checkState()

// 5. Hard reload (Ctrl+Shift+R)
// 6. Check state
await window.__cofindAuthDebug.checkState()

// Expected: User should be guest
```

### Test 2: Multiple Timeouts
```javascript
// 1. Monitor for timeouts
window.__cofindAuthDebug.monitorAuth(60000)

// 2. Navigate to pages that fetch from Supabase
// 3. Check timeout count
const summary = window.__cofindErrorTracker.getSummary()
console.log('Timeouts:', summary.timeouts.total)
```

### Test 3: Session Persistence
```javascript
// 1. Login
// 2. Save state
const state1 = await window.__cofindAuthDebug.checkState()

// 3. Refresh (F5)
// 4. Check state
const state2 = await window.__cofindAuthDebug.checkState()

// 5. Compare
console.log('State match:', 
  state1.supabaseSession?.userId === state2.supabaseSession?.userId
)
```

---

## 🔍 Advanced Debugging

### Check Supabase Storage Directly
```javascript
// Get all Supabase keys
Object.keys(localStorage).filter(k => k.includes('supabase') || k.includes('sb-'))

// Get specific key value
localStorage.getItem('sb-<project-id>-auth-token')
```

### Check Network Requests
```javascript
// Open DevTools → Network tab
// Filter by "supabase"
// Check for:
// - Failed requests (red)
// - Timeout errors
// - 401/403 errors
```

### Check Console Errors
```javascript
// All errors are logged with [Auth] prefix
// Look for:
// - [Auth] Error fetching profile
// - [Auth] Session restore failed
// - [Auth] Timeout error
```

---

## 🛠️ Emergency Fixes

### Clear Everything
```javascript
// Clear all sessions
window.__cofindAuthDebug.clearAll()

// Clear error log
window.__cofindErrorTracker.clear()

// Hard reload
location.reload(true)
```

### Force Guest Mode
```javascript
// Set logout flag
localStorage.setItem('cofind_user_logged_out', 'true')

// Clear Supabase session
await supabase.auth.signOut({ scope: 'global' })

// Clear storage
window.__cofindAuthDebug.clearAll()

// Reload
location.reload()
```

---

## 📝 Reporting Bugs

Saat melaporkan bug, sertakan:

1. **Error Log:**
```javascript
window.__cofindErrorTracker.getErrors()
```

2. **Auth State:**
```javascript
await window.__cofindAuthDebug.checkState()
```

3. **Steps to Reproduce:**
   - Login
   - Logout
   - Hard reload
   - Check state

4. **Expected vs Actual:**
   - Expected: Guest mode
   - Actual: Auto-login

---

## 🎯 Best Practices

1. **Always check state before reporting bug**
   ```javascript
   await window.__cofindAuthDebug.checkState()
   ```

2. **Monitor during testing**
   ```javascript
   window.__cofindAuthDebug.monitorAuth(30000)
   ```

3. **Check error summary regularly**
   ```javascript
   window.__cofindErrorTracker.getSummary()
   ```

4. **Export error log for analysis**
   ```javascript
   JSON.stringify(window.__cofindErrorTracker.getErrors(), null, 2)
   ```
