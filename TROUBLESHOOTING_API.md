# 🔧 Troubleshooting API Fetch Failed

## ❌ Error yang Muncul

```
[ShopList] API fetch failed, trying cache: Network failed and no valid cache available
Error loading data: Error: Unable to load coffee shops. Please check your internet connection and ensure the backend is running.
```

---

## 🔍 Diagnosis

### **Status Backend:**
✅ Backend Flask **RUNNING** di port 5000
✅ API endpoint `/api/search/coffeeshops` **RESPONDING** (28KB data)
✅ Data contains photos (60 coffee shops)

### **Kemungkinan Penyebab:**

1. ⏱️ **Timeout** - Network request timeout (5 detik)
2. 🔒 **CORS** - Browser blocking request (unlikely, tapi mungkin)
3. 💾 **Cache** - Browser cache issue
4. 🌐 **Network** - Koneksi lambat
5. 🔄 **Vite HMR** - Hot Module Replacement issue

---

## ✅ SOLUSI

### **Solusi 1: Clear Browser Cache (PALING MUDAH) ⭐**

```
1. Buka DevTools (F12)
2. Klik kanan pada Refresh button
3. Pilih "Empty Cache and Hard Reload"

Atau:

1. DevTools (F12)
2. Tab "Application"
3. "Clear storage"
4. Clear site data
5. Refresh browser (F5)
```

---

### **Solusi 2: Test API Connection**

**Buka file test yang sudah dibuat:**

```
c:\Users\User\cofind\test_frontend_api.html
```

1. Buka file di browser
2. Akan auto-run 3 tests:
   - ✅ Backend health check
   - ✅ Coffee shops API
   - ✅ CORS configuration

3. Jika semua test PASS → masalah di cache
4. Jika ada test FAIL → lihat error message

---

### **Solusi 3: Increase Timeout**

File `apiCache.js` memiliki timeout 5 detik. Jika koneksi lambat, increase timeout:

**File:** `frontend-cofind/src/utils/apiCache.js`

**Line 50 - Change:**
```javascript
// Before
setTimeout(() => reject(new Error('Network timeout')), 5000)

// After (increase to 10 seconds)
setTimeout(() => reject(new Error('Network timeout')), 10000)
```

---

### **Solusi 4: Restart Semua Service**

```bash
# 1. Stop Backend (Ctrl + C di terminal Flask)
# 2. Stop Frontend (Ctrl + C di terminal Vite)

# 3. Start Backend
cd c:\Users\User\cofind
python app.py

# 4. Start Frontend (terminal baru)
cd c:\Users\User\cofind\frontend-cofind
npm run dev

# 5. Hard Refresh Browser
Ctrl + Shift + R
```

---

### **Solusi 5: Check .env.local**

Pastikan file `.env.local` berisi:

```env
VITE_USE_API=true
VITE_API_BASE=http://localhost:5000
```

**Verify:**
```bash
cd frontend-cofind
type .env.local
```

---

### **Solusi 6: Disable Service Worker (Temporary)**

Service Worker mungkin interfere dengan requests.

**File:** `frontend-cofind/src/utils/sw-register.js`

Sudah disabled di development mode, tapi jika masih issue:

1. DevTools (F12)
2. Tab "Application"
3. "Service Workers"
4. Unregister all service workers
5. Refresh browser

---

### **Solusi 7: Check CORS in app.py**

**File:** `cofind/app.py`

**Pastikan CORS enabled:**
```python
# Line ~15
from flask_cors import CORS

# Line ~90
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

Jika ada perubahan, restart Flask:
```bash
# Ctrl + C untuk stop
python app.py
```

---

## 🔬 Advanced Debugging

### **Check Browser Console (F12):**

1. **Tab Console** - Lihat error messages
2. **Tab Network** - Filter: `Fetch/XHR`
3. Look for request ke `localhost:5000`
4. Check status code:
   - ✅ **200** = Success
   - ❌ **0** = CORS/Network issue
   - ❌ **404** = Endpoint not found
   - ❌ **500** = Backend error
   - ❌ **(failed)** = Request blocked/timeout

### **Check Flask Console:**

Saat frontend fetch, Flask harus log:
```
127.0.0.1 - - [DATE] "GET /api/search/coffeeshops?lat=-0.026330&lng=109.342506 HTTP/1.1" 200 -
```

Jika tidak ada log → request tidak sampai ke backend

---

## 📊 Test Matrix

| Test | How to Check | Expected Result |
|------|--------------|-----------------|
| Backend Running | `curl http://localhost:5000` | 200 OK |
| API Endpoint | `curl http://localhost:5000/api/search/coffeeshops?lat=-0.026330&lng=109.342506` | 200 OK, data array |
| Frontend .env | `type .env.local` | VITE_USE_API=true |
| Browser Console | F12 → Console | No red errors |
| Network Tab | F12 → Network → XHR | Status 200 |

---

## 🎯 Quick Fix Steps

### **Langkah 1: Verify Backend**
```bash
curl http://localhost:5000/
# Should return: {"message":"Welcome to COFIND API"}
```

### **Langkah 2: Clear Browser Cache**
```
F12 → Right-click Refresh → Empty Cache and Hard Reload
```

### **Langkah 3: Test with HTML File**
```
Open: c:\Users\User\cofind\test_frontend_api.html
Check if all tests pass
```

### **Langkah 4: Check Console**
```
F12 → Console
Look for:
✅ "[ShopList] Loading from API (network)"
❌ "[ShopList] API fetch failed"
```

---

## 💡 Most Common Solution

**90% kasus solved dengan:**

1. **Clear browser cache** (Ctrl + Shift + R)
2. **Restart Vite** (Ctrl + C, npm run dev)
3. **Hard refresh** (F5)

**Jika masih error:**

4. **Restart Flask** (Ctrl + C, python app.py)
5. **Clear storage** (F12 → Application → Clear storage)
6. **Refresh browser** (F5)

---

## 🔍 Debug Code (Add to ShopList.jsx)

Jika masih debug, tambahkan console.log:

**File:** `frontend-cofind/src/pages/ShopList.jsx`

**Line ~133 (before fetch):**
```javascript
console.log('[DEBUG] USE_API:', USE_API);
console.log('[DEBUG] isOnline:', isOnline);
console.log('[DEBUG] API_BASE:', API_BASE);
console.log('[DEBUG] API URL:', apiUrl);
```

**Line ~145 (after error):**
```javascript
console.error('[DEBUG] API Error:', apiError);
console.error('[DEBUG] Error details:', {
  message: apiError.message,
  name: apiError.name,
  stack: apiError.stack
});
```

Restart Vite, refresh, check console untuk detail error.

---

## 📞 Still Not Working?

Jika setelah semua langkah masih error:

1. Screenshot error di console (F12)
2. Screenshot network tab (F12 → Network)
3. Copy Flask console output
4. Check if:
   - ✅ Backend running: `python app.py`
   - ✅ Frontend running: `npm run dev`
   - ✅ `.env.local` exists with correct values
   - ✅ Browser can access `http://localhost:5000`

---

## ✅ Success Indicators

Ketika berhasil, console harus menunjukkan:

```
[SW Register] Development mode detected - Service Worker disabled untuk HMR
[API Cache] Database initialized
[ShopList] Loading from API (network) ✅
[API Cache] Data fetched from network and cached: http://localhost:5000/api/search/coffeeshops?lat=-0.026330&lng=109.342506
[ShopList] Featured images preloaded successfully
```

Dan web menampilkan:
- 📊 Statistics cards
- 🏆 Featured coffee shops dengan foto
- 🏷️ Filter categories
- 📋 Coffee shop catalog dengan foto

---

**Created:** November 2025  
**Status:** Backend ✅ Running | Frontend ❌ Fetch Failed  
**Next Action:** Clear browser cache & hard reload

