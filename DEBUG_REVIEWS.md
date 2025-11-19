# 🔍 Debug Reviews - Pastikan LLM Mengutip Review Asli dari Places API

## 🎯 Tujuan

Memastikan bahwa LLM **MENGUTIP PERSIS** review asli dari Google Places API, bukan membuat review sendiri atau mengubah isi review.

---

## ✅ Perbaikan yang Diimplementasikan

### 1️⃣ **System Prompt Diperkuat (COPY-PASTE Instruction)**

**Instruksi Baru:**
```
INSTRUKSI WAJIB:
2. WAJIB KUTIP REVIEW PERSIS dari data di atas - COPY PASTE review asli
3. Format kutipan: "Teks review ASLI dari data" - Nama User ASLI (Rating⭐)
5. DILARANG mengubah, meringkas, atau membuat review sendiri
6. DILARANG membuat nama user palsu (gunakan nama ASLI dari data)
7. Review harus WORD-FOR-WORD dari data yang diberikan

CARA MENGUTIP REVIEW YANG BENAR:
- Lihat data di atas, cari bagian "Review dari Pengunjung:"
- COPY PASTE teks review PERSIS seperti di data
- Gunakan nama user PERSIS seperti di data
- Sertakan rating PERSIS seperti di data

CONTOH CARA KUTIP:
Data: "- John Doe (5⭐): "Tempatnya sangat nyaman untuk bekerja""
Kutip: • "Tempatnya sangat nyaman untuk bekerja" - John Doe (5⭐)
```

**Key Changes:**
- ✅ Kata "COPY PASTE" untuk emphasize
- ✅ "WORD-FOR-WORD" untuk clarity
- ✅ Contoh konkret cara mengutip
- ✅ DILARANG mengubah atau meringkas

---

### 2️⃣ **Debug Logging Added**

**Console Output:**
```python
print(f"[LLM] Context preview (first 500 chars):")
print(places_context[:500])
print(f"[LLM] Total context length: {len(places_context)} characters")
```

**Berguna untuk:**
- ✅ Verify review benar-benar ada di context
- ✅ Check format review di context
- ✅ Ensure data dari Places API masuk

---

### 3️⃣ **Debug Endpoint Added** ⭐

**New Endpoint:**
```
GET /api/debug/reviews-context?location=Pontianak&max_shops=5
```

**Response:**
```json
{
  "status": "success",
  "location": "Pontianak",
  "max_shops": 5,
  "context_length": 5432,
  "context_preview": "DAFTAR COFFEE SHOP DI PONTIANAK...",
  "full_context": "...complete context with all reviews..."
}
```

**Use Case:**
- ✅ Lihat review asli yang dikirim ke LLM
- ✅ Verify nama user & review text
- ✅ Compare dengan output LLM
- ✅ Debug jika LLM tidak kutip dengan benar

---

## 🧪 Cara Debug & Verify

### **Step 1: Lihat Raw Review Context**

```bash
# PowerShell/Terminal
curl "http://localhost:5000/api/debug/reviews-context?location=Pontianak&max_shops=3"

# Atau buka di browser:
http://localhost:5000/api/debug/reviews-context?location=Pontianak&max_shops=3
```

**Expected Output:**
```json
{
  "full_context": "
DAFTAR COFFEE SHOP DI PONTIANAK DENGAN REVIEW
Total: 3 coffee shop pilihan terbaik

1. Kopi Kenangan
   • Rating: 4.7/5.0 (234 reviews)
   • Harga: 💰💰 (Level 2/4)
   • Alamat: Jl. Gajah Mada No. 123, Pontianak
   • Review dari Pengunjung:
     - Sarah Wijaya (5⭐): \"Tempatnya sangat nyaman untuk kerja, wifi kencang dan colokan di setiap meja!\"
     - Budi Santoso (4⭐): \"Harga affordable banget, kopinya enak, suasana tenang cocok buat fokus\"
..."
}
```

**Catat:**
- ✅ Nama user: Sarah Wijaya, Budi Santoso
- ✅ Review text lengkap
- ✅ Rating: 5⭐, 4⭐

---

### **Step 2: Test AI Analyzer**

1. Buka `http://localhost:5173/ai-analyzer`
2. Input preferensi:
   ```
   Saya mencari coffee shop yang cozy, tenang, cocok untuk kerja,
   ada wifi cepat dan harga terjangkau
   ```
3. Click "Dapatkan Rekomendasi"
4. Tunggu response (~10-15 detik)

---

### **Step 3: Verify Output**

**Check apakah LLM mengutip PERSIS:**

✅ **CORRECT Example:**
```
📝 Bukti dari Review Pengunjung:
• "Tempatnya sangat nyaman untuk kerja, wifi kencang dan colokan di setiap meja!" - Sarah Wijaya (5⭐)
• "Harga affordable banget, kopinya enak, suasana tenang cocok buat fokus" - Budi Santoso (4⭐)
```

❌ **INCORRECT Example (Hallucination):**
```
📝 Bukti dari Review Pengunjung:
• "Tempat bagus untuk kerja" - User A (5⭐)  ← Nama generic!
• "Kopinya enak" - Pengunjung (4⭐)  ← Review dipendekkan!
```

---

### **Step 4: Compare Context vs Output**

1. **Context dari Backend:**
   ```
   - Sarah Wijaya (5⭐): "Tempatnya sangat nyaman untuk kerja, wifi kencang dan colokan di setiap meja!"
   ```

2. **Output LLM (BENAR):**
   ```
   • "Tempatnya sangat nyaman untuk kerja, wifi kencang dan colokan di setiap meja!" - Sarah Wijaya (5⭐)
   ```

3. **Output LLM (SALAH):**
   ```
   • "Tempat nyaman untuk kerja dengan wifi" - Sarah (5⭐)  ← DIRINGKAS!
   ```

**Validation:**
- ✅ Nama SAMA (Sarah Wijaya, bukan "Sarah" atau "User A")
- ✅ Text SAMA (word-for-word, bukan summary)
- ✅ Rating SAMA (5⭐)

---

## 🔧 Troubleshooting

### **Problem 1: LLM Tidak Mengutip Review**

**Symptoms:**
- Output hanya berisi deskripsi, tanpa review
- Atau review sangat generic

**Solution:**
```bash
# 1. Check apakah review ada di context
curl "http://localhost:5000/api/debug/reviews-context?location=Pontianak&max_shops=3"

# 2. Verify output contains "Review dari Pengunjung:"
# 3. Jika tidak ada, check Google Places API key & billing
```

---

### **Problem 2: LLM Membuat Nama User Palsu**

**Symptoms:**
- Nama user generic: "User A", "Pengunjung 1", "Customer"
- Bukan nama asli dari Places API

**Root Cause:**
- LLM tidak baca context dengan teliti
- Context terlalu panjang (> model's context window)

**Solution:**
```python
# app.py - Reduce max_shops
_fetch_coffeeshops_with_reviews_context(
    location,
    max_shops=5  # Reduce dari 10 ke 5
)
```

---

### **Problem 3: Review Diringkas atau Diubah**

**Symptoms:**
```
Context: "Tempatnya sangat nyaman untuk kerja, wifi kencang..."
Output: "Tempat nyaman untuk kerja" ← DIRINGKAS!
```

**Root Cause:**
- LLM temperature terlalu tinggi (creative mode)
- Max tokens terlalu kecil (LLM shortcuts)

**Solution:**
```python
# app.py line ~705-707
max_tokens=1024,     # Sudah cukup
temperature=0.3,     # LOWER dari 0.5 → more factual
top_p=0.9
```

---

### **Problem 4: Review Tidak Relevan dengan Preferensi**

**Symptoms:**
- User minta "wifi cepat"
- LLM kutip review tentang "kopi enak" (tidak relevan)

**Solution:**
- Ini ACCEPTABLE! Asalkan review ASLI dari data
- LLM challenge: pilih review yang relevan
- User tetap mendapat transparansi penuh

---

## 📊 Validation Checklist

Setelah mendapat output dari AI Analyzer:

### **Review Authenticity:**
- [ ] Nama user bukan generic (bukan "User A", "Pengunjung")
- [ ] Nama user match dengan data di debug endpoint
- [ ] Review text match word-for-word (boleh cut di "...")
- [ ] Rating match (5⭐, 4⭐, dll)

### **Review Quality:**
- [ ] Minimal 2 review per rekomendasi
- [ ] Review relevan dengan preferensi user
- [ ] Penjelasan "Mengapa Cocok" mention poin dari review

### **Format:**
- [ ] Format: `"Review text" - Nama User (X⭐)`
- [ ] Menggunakan emoji ⭐ untuk rating
- [ ] Tanda kutip untuk review text

---

## 🎯 Expected vs Actual Comparison

### **Test Case: Wifi & Cozy Preference**

**Input:**
```
Saya mencari coffee shop yang cozy dan ada wifi cepat
```

**Debug Context (from `/api/debug/reviews-context`):**
```
1. Kopi Kenangan
   • Review dari Pengunjung:
     - Sarah Wijaya (5⭐): "Tempatnya sangat nyaman untuk kerja, wifi kencang dan colokan di setiap meja!"
     - Budi Santoso (4⭐): "Suasana cozy banget, cocok buat WFH. Wifi stabil."
```

**Expected LLM Output:**
```
🏆 Kopi Kenangan - Rating 4.7/5.0

✅ Mengapa Cocok:
Coffee shop ini memenuhi kriteria Anda dengan suasana cozy
dan wifi yang sangat cepat...

📝 Bukti dari Review Pengunjung:
• "Tempatnya sangat nyaman untuk kerja, wifi kencang dan colokan di setiap meja!" - Sarah Wijaya (5⭐)
• "Suasana cozy banget, cocok buat WFH. Wifi stabil." - Budi Santoso (4⭐)
```

**Validation:**
- ✅ Review 1: EXACT match with context
- ✅ Review 2: EXACT match with context
- ✅ Names: Sarah Wijaya, Budi Santoso (EXACT)
- ✅ Ratings: 5⭐, 4⭐ (EXACT)
- ✅ Relevance: Both mention wifi/cozy

---

## 🚀 Quick Debug Commands

### **1. View Raw Context:**
```bash
curl "http://localhost:5000/api/debug/reviews-context?location=Pontianak&max_shops=3" | jq '.full_context'
```

### **2. Clear Cache & Refetch:**
```bash
curl -X POST http://localhost:5000/api/cache/clear
```

### **3. Check Cache Status:**
```bash
curl "http://localhost:5000/api/cache/status"
```

### **4. Test Endpoint:**
```bash
curl "http://localhost:5000/api/test"
```

---

## 📝 Advanced: Log Analysis

### **Backend Logs to Check:**

1. **Context Fetching:**
   ```
   [PLACES+REVIEWS] Fetching coffee shops with reviews for: Pontianak
   [PLACES+REVIEWS] Found 10 coffee shops, fetching details...
   [PLACES+REVIEWS] Fetching details for 1/10: Kopi Kenangan
   ```

2. **Review Count:**
   ```
   [PLACES+REVIEWS] Context prepared: 10 shops with reviews, 12543 characters
   ```

3. **LLM Context:**
   ```
   [LLM] Context preview (first 500 chars):
   DAFTAR COFFEE SHOP DI PONTIANAK DENGAN REVIEW
   Total: 10 coffee shop pilihan terbaik...
   ```

4. **LLM Response:**
   ```
   [LLM] Generated text: 🏆 Kopi Kenangan...
   ```

---

## 🎯 Success Criteria

✅ **Review Authentication:** Nama user & text match 100% dengan data  
✅ **No Hallucination:** Tidak ada review atau nama yang dibuat-buat  
✅ **Transparency:** User bisa verify review di halaman detail coffee shop  
✅ **Consistency:** Semua rekomendasi punya bukti review lengkap  

---

## 📞 Next Steps

Jika masih ada issue:

1. **Check Context:**
   ```bash
   curl "http://localhost:5000/api/debug/reviews-context?location=Pontianak&max_shops=3"
   ```

2. **Compare dengan ShopDetail:**
   - Buka halaman detail coffee shop
   - Lihat review yang ditampilkan
   - Should SAMA dengan context

3. **Adjust LLM Temperature:**
   ```python
   temperature=0.3  # Very factual
   temperature=0.5  # Balanced
   temperature=0.7  # More creative (not recommended)
   ```

4. **Report Issue:**
   - Screenshot output LLM
   - Copy context dari debug endpoint
   - Show comparison

---

**Status:** ✅ **READY FOR TESTING**  
**Date:** January 2025

🔍 **Debugging tools ready - pastikan review 100% asli dari Places API!**

