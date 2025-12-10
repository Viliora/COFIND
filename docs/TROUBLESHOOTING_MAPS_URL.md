# 🔧 Troubleshooting: URL Google Maps Tidak Muncul

## 🚨 Problem
User melaporkan bahwa **URL Google Maps tidak muncul** atau **tidak bisa diklik** di halaman AI Analyzer.

---

## ✅ Solusi & Langkah Perbaikan

### **Langkah 1: Restart Flask Server** ⚠️ PENTING!

Perubahan kode di `app.py` **TIDAK akan ter-load** sampai server di-restart.

```bash
# Stop Flask server (tekan Ctrl+C di terminal yang running Flask)
# Atau gunakan PowerShell:
Get-Process python | Where-Object {$_.CommandLine -match "app.py"} | Stop-Process -Force

# Restart Flask
python app.py
```

**Kenapa harus restart?**
- Flask dev server perlu reload kode Python
- Cache lama masih di memory
- Field baru di API request (`place_id`, `user_ratings_total`) belum aktif

---

### **Langkah 2: Clear Cache**

Setelah restart server, clear cache untuk fetch data fresh:

```bash
# Menggunakan API endpoint
curl -X POST http://localhost:5000/api/cache/clear -H "Content-Type: application/json" -d "{}"

# Atau menggunakan Python
python -c "import requests; print(requests.post('http://localhost:5000/api/cache/clear', json={}).json())"
```

**Expected Output:**
```json
{
  "status": "success",
  "message": "All cache cleared",
  "remaining_cached_locations": 0
}
```

---

### **Langkah 3: Verify Context Data**

Test apakah URL Google Maps ada dalam context yang dikirim ke LLM:

```bash
# Menggunakan debug endpoint
python -c "import requests; r = requests.get('http://localhost:5000/api/debug/reviews-context?location=Pontianak'); print('Google Maps URL found:' if 'Google Maps:' in r.text else 'NOT FOUND'); print(r.json()['full_context'][:1000])"
```

**Expected Output (harus ada):**
```
1. Paskamasala
   • Rating: 4.7/5.0 (311 reviews)
   • Harga: 💰💰 (Level 2/4)
   • Alamat: Gg. Sukarame No.10, Sungai Bangkong...
   • Google Maps: https://www.google.com/maps/place/?q=place_id:ChIJ...
   • Review dari Pengunjung:
     - Chintamy Christini (5⭐): "Salah satu cafe hits..."
```

✅ **Jika muncul**: Context sudah benar, lanjut ke Langkah 4
❌ **Jika TIDAK muncul**: Ada masalah di backend, cek logs Flask

---

### **Langkah 4: Test LLM Output**

Test apakah LLM menyertakan URL dalam output:

```bash
python -c "import requests; r = requests.post('http://localhost:5000/api/llm/analyze', json={'text': 'wifi bagus', 'task': 'recommend', 'location': 'Pontianak'}); print('Maps URL in output:', 'google.com/maps' in r.json()['analysis'].lower()); print(r.json()['analysis'][:800])"
```

**Expected Output (harus ada URL):**
```
🏆 Paskamasala - Rating 4.7/5.0
📍 Alamat: Gg. Sukarame No.10, Sungai Bangkong...
🗺️ Google Maps: https://www.google.com/maps/place/?q=place_id:ChIJ...
💰 Harga: 💰💰
```

✅ **Jika muncul**: Backend & LLM bekerja dengan baik, masalah di frontend
❌ **Jika TIDAK muncul**: LLM tidak mengikuti instruksi, cek prompt

---

### **Langkah 5: Test Frontend Rendering**

Buka browser Developer Tools (F12) dan test function `renderTextWithBold`:

```javascript
// Test di Console browser
const testText = "📍 Alamat: Pontianak\n🗺️ Google Maps: https://www.google.com/maps/place/?q=place_id:ChIJ123";

// Regex yang digunakan
const pattern = /(\*\*[^*]+\*\*|https?:\/\/[^\s]+)/g;
console.log("Parts:", testText.split(pattern));

// Should output: ["📍 Alamat: Pontianak\n🗺️ Google Maps: ", "https://www.google.com/maps/place/?q=place_id:ChIJ123", ""]
```

✅ **Jika split benar**: Function bisa detect URL
❌ **Jika split salah**: Ada bug di regex, perlu fix

---

## 🧪 Automated Test Script

Gunakan script test otomatis:

```bash
python test_maps_url.py
```

Script ini akan:
1. ✅ Clear cache
2. ✅ Check debug context
3. ✅ Test LLM endpoint
4. ✅ Verify frontend capability

**Expected Output:**
```
🧪 TEST GOOGLE MAPS URL INTEGRATION
======================================================================

[TEST 1] Clearing cache...
✅ Cache cleared successfully

[TEST 2] Checking debug reviews context...
   • Context length: 2831 characters
   • Contains 'Google Maps:': True
   • Contains 'https://www.google.com/maps/': True
   • Contains 'place_id:': True
✅ Google Maps URL found in context!

[TEST 3] Testing LLM analyze endpoint...
   • Response length: 1453 characters
   • Contains Google Maps reference: True
   • Contains maps emoji (🗺️): True
✅ Google Maps URL appears in LLM output!

[TEST 4] Frontend URL rendering check...
   ✅ LLMAnalyzer.jsx has renderTextWithBold() function
```

---

## 🔍 Diagnosis Flowchart

```
User: "URL Maps tidak muncul"
    │
    ├─> Sudah restart Flask server?
    │   ├─ No  → RESTART FLASK (Langkah 1)
    │   └─ Yes → Lanjut
    │
    ├─> Sudah clear cache?
    │   ├─ No  → CLEAR CACHE (Langkah 2)
    │   └─ Yes → Lanjut
    │
    ├─> URL ada di debug context?
    │   ├─ No  → Check backend logs, verify get_place_details()
    │   └─ Yes → Lanjut
    │
    ├─> URL ada di LLM output?
    │   ├─ No  → LLM tidak ikuti prompt, perlu strengthen
    │   └─ Yes → Lanjut
    │
    └─> URL tidak clickable di frontend?
        └─ Check renderTextWithBold(), verify regex pattern
```

---

## 🐛 Common Issues & Fixes

### **Issue 1: `place_id` field missing**

**Symptom:** Error di console: `'NoneType' object has no attribute 'place_id'`

**Fix:** Pastikan field `place_id` ada di `get_place_details()`:

```python
params = {
    'place_id': place_id,
    'fields': 'place_id,name,rating,formatted_phone_number,...',  # MUST include place_id
    'key': GOOGLE_PLACES_API_KEY
}
```

---

### **Issue 2: Cache lama masih aktif**

**Symptom:** Data lama tanpa URL Maps masih muncul meski kode sudah diupdate

**Fix:**
```bash
# Clear cache via API
curl -X POST http://localhost:5000/api/cache/clear -H "Content-Type: application/json" -d "{}"

# Check cache status
curl http://localhost:5000/api/cache/status
```

---

### **Issue 3: URL tidak clickable di frontend**

**Symptom:** URL muncul tapi sebagai plain text, tidak bisa diklik

**Fix:** Verify function `renderTextWithBold` di `LLMAnalyzer.jsx`:

```javascript
// CORRECT regex pattern
const parts = text.split(/(\*\*[^*]+\*\*|https?:\/\/[^\s]+)/g);

// Check untuk URL
if (part.match(/^https?:\/\/[^\s]+$/)) {
  return (
    <a href={part} target="_blank" rel="noopener noreferrer"
       className="text-blue-600 underline">
      {part}
    </a>
  );
}
```

---

### **Issue 4: LLM tidak include URL dalam output**

**Symptom:** URL ada di context tapi LLM tidak menampilkannya

**Fix:** Check prompt di `/api/llm/analyze`:

```python
FORMAT WAJIB untuk setiap rekomendasi:
🏆 [Nama Coffee Shop] - Rating X/5.0
📍 Alamat: [alamat lengkap]
🗺️ Google Maps: [URL dari data]  # ← MUST be in prompt
💰 Harga: [level harga]
```

Jika LLM masih ignore:
1. Increase `temperature` di LLM call (dari 0.5 ke 0.6)
2. Add CAPS emphasis: **"WAJIB SERTAKAN URL GOOGLE MAPS"**
3. Add example in system prompt

---

### **Issue 5: CORS error di frontend**

**Symptom:** Browser console shows CORS error saat fetch API

**Fix:** Verify CORS di `app.py`:

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS untuk semua routes
```

---

## 📊 Verification Checklist

Gunakan checklist ini untuk verify semua komponen:

### **Backend:**
- [ ] `app.py` line 316: Field `place_id` dan `user_ratings_total` included
- [ ] `app.py` line 424-427: Generate `maps_url` dari `place_id`
- [ ] `app.py` line 436: Append `maps_url` ke context_lines
- [ ] `app.py` line 705: Prompt includes "🗺️ Google Maps: [URL dari data]"
- [ ] Flask server restarted after code changes
- [ ] Cache cleared via `/api/cache/clear`

### **API Response:**
- [ ] `/api/debug/reviews-context` shows "Google Maps: https://..."
- [ ] `/api/llm/analyze` output includes "Google Maps: https://..."
- [ ] URL format: `https://www.google.com/maps/place/?q=place_id:ChIJ...`

### **Frontend:**
- [ ] `LLMAnalyzer.jsx` line 18: Regex includes `|https?:\/\/[^\s]+`
- [ ] `LLMAnalyzer.jsx` line 31-40: URL match returns `<a>` tag
- [ ] `<a>` tag has `target="_blank"` and `rel="noopener noreferrer"`
- [ ] Tailwind classes: `text-blue-600`, `underline`, `hover:text-blue-800`
- [ ] Browser console shows no errors

### **User Experience:**
- [ ] URL visible di setiap rekomendasi coffee shop
- [ ] URL berwarna biru dengan underline
- [ ] Hover effect bekerja (warna berubah)
- [ ] Klik URL membuka Google Maps di tab baru
- [ ] Mobile: Tap URL membuka Google Maps app

---

## 🎯 Quick Fix Summary

**Problem:** URL Maps tidak muncul atau tidak clickable

**Solution (5 menit):**

```bash
# 1. Restart Flask
# Stop server (Ctrl+C), then:
python app.py

# 2. Clear cache (wait for Flask to start)
python -c "import requests; print(requests.post('http://localhost:5000/api/cache/clear', json={}).json())"

# 3. Test (seharusnya muncul "True")
python -c "import requests; r = requests.get('http://localhost:5000/api/debug/reviews-context?location=Pontianak'); print('Google Maps found:', 'Google Maps:' in r.text)"

# 4. Refresh browser di halaman AI Analyzer
# 5. Input keyword dan klik Analisis
# 6. Verify URL muncul dan bisa diklik
```

---

## 📞 Support

Jika masih bermasalah setelah semua langkah:

1. **Check Flask logs** untuk error messages
2. **Check browser console** (F12) untuk JavaScript errors
3. **Run test script:** `python test_maps_url.py`
4. **Verify API key** masih valid (quota tidak habis)

---

**Last Updated:** November 20, 2024
**Status:** ✅ Fixed and verified

