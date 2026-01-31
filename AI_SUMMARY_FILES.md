# 📝 File-file untuk Mengubah Logic AI Summary

Dokumentasi ini menjelaskan file-file yang perlu diperhatikan jika Anda ingin mengubah logic untuk hasil AI summary di project COFIND.

---

## 🎯 Ringkasan

Ada **2 endpoint utama** untuk AI summary:
1. **`/api/coffeeshops/<place_id>/summarize`** - Summary dengan keywords (3 keywords positif)
2. **`/api/llm/summarize-review`** - Summary review dari reviews.json (15-30 kata)

---

## 📂 File-file yang Perlu Diperhatikan

### 🔴 **1. Backend - `app.py`** (PENTING!)

#### **A. Endpoint: `/api/coffeeshops/<place_id>/summarize`** (Line 805-1101)

**Lokasi:** `app.py` line 805-1101

**Fungsi:** Generate AI summary untuk coffee shop dengan 3 keywords positif (maksimal 100 karakter)

**Bagian-bagian yang bisa diubah:**

1. **Keyword Extraction (Line 859-905)**
   - **Prompt untuk ekstraksi keywords:** Line 871-886
   - **Model parameters:** Line 890-896
     - `max_new_tokens=50`
     - `temperature=0.4`
   - **Parsing keywords:** Line 899-900

2. **Fallback ke Facilities.json (Line 906-963)**
   - **Keyword mapping:** Line 922-937
   - **Logic untuk mengambil dari highlights, popular_for, atmosphere**

3. **Summary Generation (Line 976-1075)**
   - **System instruction:** Line 980-983
     ```python
     system_instruction = """Kamu adalah asisten yang membuat ringkasan objektif tentang coffee shop.
     Format WAJIB: "{Nama Coffee Shop} adalah coffee shop yang memiliki {deskripsi singkat berdasarkan keywords}."
     JANGAN gunakan sapaan atau gaya promosi.
     Output HANYA ringkasan dalam 1 kalimat, maksimal 100 karakter."""
     ```
   - **User prompt:** Line 986-994
   - **Model parameters:** Line 1012-1017
     - `max_new_tokens=150`
     - `temperature=0.4`
   - **Response cleaning:** Line 1020-1034
   - **Truncation:** Line 1084-1085 (maksimal 100 karakter)

**Yang bisa diubah:**
- ✅ Format output summary (system instruction)
- ✅ Panjang maksimal summary (100 karakter)
- ✅ Jumlah keywords (saat ini 3)
- ✅ Prompt untuk keyword extraction
- ✅ Prompt untuk summary generation
- ✅ Model parameters (temperature, max_tokens)
- ✅ Post-processing logic (cleaning response)

---

#### **B. Endpoint: `/api/llm/summarize-review`** (Line 3154-3363)

**Lokasi:** `app.py` line 3154-3363

**Fungsi:** Generate ringkasan review dari reviews.json (15-30 kata, tanpa nama coffee shop di awal)

**Bagian-bagian yang bisa diubah:**

1. **Data Source (Line 3188-3208)**
   - **File reviews.json:** Line 3189
   - **Jumlah review untuk context:** Line 3211 (saat ini 10 review terbaru)

2. **System Prompt (Line 3230-3261)**
   - **ATURAN KETAT untuk format summary:**
     - Maksimal 1 kalimat, 15-30 kata
     - Tidak boleh nama coffee shop di awal
     - Tidak boleh frasa pembuka tertentu
     - Contoh format yang benar dan salah
   
   **Ini adalah bagian PENTING untuk mengubah format output!**

3. **User Prompt (Line 3264)**
   - Instruksi untuk generate summary

4. **LLM API Call (Line 3270-3279)**
   - **Model parameters:**
     - `max_tokens=100`
     - `temperature=0.3`
     - `top_p=0.85`

5. **Post-processing (Line 3283-3335)**
   - **Hapus quotes:** Line 3284
   - **Hapus nama coffee shop di awal:** Line 3290-3294
   - **Hapus frasa pembuka yang tidak diinginkan:** Line 3297-3318
   - **Capitalize huruf pertama:** Line 3320-3322
   - **Truncate jika terlalu panjang:** Line 3324-3335 (maksimal 30 kata)

**Yang bisa diubah:**
- ✅ Format output summary (system prompt)
- ✅ Panjang maksimal summary (15-30 kata)
- ✅ Jumlah review untuk context (saat ini 10)
- ✅ Frasa pembuka yang dilarang (unwanted_prefixes)
- ✅ Model parameters (temperature, max_tokens, top_p)
- ✅ Post-processing logic (cleaning, truncation)

---

### 🟡 **2. Frontend - `frontend-cofind/src/utils/reviewSummary.js`**

**Lokasi:** `frontend-cofind/src/utils/reviewSummary.js`

**Fungsi:** Utility untuk fetch dan cache review summary dari backend

**Bagian-bagian yang bisa diubah:**

1. **API Endpoint (Line 56)**
   ```javascript
   const response = await fetch(`${API_BASE}/api/llm/summarize-review`, {
   ```
   - Endpoint yang dipanggil: `/api/llm/summarize-review`

2. **Cache Management (Line 22-47)**
   - **Cache version:** Line 4 (`CACHE_VERSION = 'v3'`)
   - **Cache duration:** Line 5 (7 hari)
   - **Cache key format:** Line 22 (`review_summary_${placeId}`)

3. **Post-processing di Frontend (Line 117-151)**
   - **Hapus nama coffee shop:** Line 121-123
   - **Hapus frasa pembuka:** Line 127-146
   - **Capitalize:** Line 149-150
   
   **Note:** Saat ini banyak bagian yang di-comment (Line 55-172), jadi post-processing utama ada di backend.

**Yang bisa diubah:**
- ✅ Endpoint API yang dipanggil
- ✅ Cache version (untuk invalidate cache lama)
- ✅ Cache duration
- ✅ Post-processing logic (jika ingin cleaning di frontend juga)

---

### 🟢 **3. Frontend - `frontend-cofind/src/components/CoffeeShopCard.jsx`**

**Lokasi:** `frontend-cofind/src/components/CoffeeShopCard.jsx`

**Fungsi:** Component yang menampilkan coffee shop card dan menggunakan AI summary

**Bagian-bagian yang relevan:**

1. **Fetch Review Summary (Line 27-40)**
   - Menggunakan `getReviewSummary()` dari `reviewSummary.js`
   - Endpoint: `/api/llm/summarize-review`

2. **Fetch AI Summary (Line 47-80)**
   - **Endpoint yang dipanggil:** Line 59
     ```javascript
     const response = await fetch(`http://localhost:5000/api/coffeeshops/${shop.place_id}/summarize`, {
     ```
   - **Method:** POST
   - **Display logic:** Line 67-76

3. **Display Summary (Line 168-246)**
   - **Review Summary display:** Line 174-183
   - **AI Summary bubble:** Line 224-246

**Yang bisa diubah:**
- ✅ Endpoint API yang dipanggil (jika ingin menggunakan endpoint berbeda)
- ✅ Display format summary
- ✅ Error handling
- ✅ Loading states

---

### 🔵 **4. Frontend - `frontend-cofind/src/components/SmartReviewSummary.jsx`**

**Lokasi:** `frontend-cofind/src/components/SmartReviewSummary.jsx`

**Status:** Saat ini component ini kosong (hanya return null)

**Kemungkinan penggunaan:**
- Component ini mungkin direncanakan untuk menampilkan smart summary dengan analisis sentimen
- Bisa digunakan untuk implementasi summary logic yang lebih advanced

**Yang bisa diubah:**
- ✅ Implementasi component untuk smart summary
- ✅ Integrasi dengan endpoint AI summary

---

## 🔧 Cara Mengubah Logic AI Summary

### **Skenario 1: Mengubah Format Output Summary**

**File yang perlu diubah:**
1. **`app.py`** - Endpoint `/api/llm/summarize-review`
   - **System prompt (Line 3230-3261):** Ubah aturan format output
   - **Post-processing (Line 3286-3335):** Sesuaikan cleaning logic

**Contoh perubahan:**
```python
# Di system_prompt, ubah aturan:
system_prompt = f"""Anda adalah asisten yang ahli dalam meringkas review coffee shop. 
Tugas Anda adalah membuat ringkasan SINGKAT (maksimal 2 kalimat, 40-60 kata) yang menonjolkan keunikan...

# Ubah maksimal kata:
if len(words) > 60:  # Ubah dari 30 ke 60
```

---

### **Skenario 2: Mengubah Panjang Summary**

**File yang perlu diubah:**
1. **`app.py`** - Endpoint `/api/coffeeshops/<place_id>/summarize`
   - **Truncation (Line 1084-1085):** Ubah dari 100 karakter
   
2. **`app.py`** - Endpoint `/api/llm/summarize-review`
   - **System prompt (Line 3234):** Ubah "15-30 kata"
   - **Truncation (Line 3326):** Ubah dari 30 kata

---

### **Skenario 3: Mengubah Jumlah Keywords**

**File yang perlu diubah:**
1. **`app.py`** - Endpoint `/api/coffeeshops/<place_id>/summarize`
   - **Keyword extraction prompt (Line 876):** Ubah "TEPAT 3 keywords"
   - **Final keywords (Line 965):** Ubah `[:3]` menjadi jumlah yang diinginkan
   - **Generic keywords fallback (Line 968-972):** Sesuaikan jumlah

---

### **Skenario 4: Mengubah Model Parameters**

**File yang perlu diubah:**
1. **`app.py`** - Endpoint `/api/coffeeshops/<place_id>/summarize`
   - **Keyword extraction (Line 890-896):**
     ```python
     max_new_tokens=50,  # Ubah sesuai kebutuhan
     temperature=0.4,    # Ubah untuk lebih kreatif (0.7-0.9) atau lebih deterministik (0.1-0.3)
     ```
   - **Summary generation (Line 1012-1017):**
     ```python
     max_new_tokens=150,  # Ubah sesuai kebutuhan
     temperature=0.4,      # Ubah sesuai kebutuhan
     ```

2. **`app.py`** - Endpoint `/api/llm/summarize-review`
   - **LLM API call (Line 3276-3278):**
     ```python
     max_tokens=100,     # Ubah sesuai kebutuhan
     temperature=0.3,   # Ubah untuk lebih kreatif atau deterministik
     top_p=0.85,        # Ubah untuk lebih fokus atau lebih beragam
     ```

---

### **Skenario 5: Mengubah Post-processing Logic**

**File yang perlu diubah:**
1. **`app.py`** - Endpoint `/api/llm/summarize-review`
   - **Unwanted prefixes (Line 3297-3311):** Tambah/hapus frasa yang tidak diinginkan
   - **Truncation logic (Line 3324-3335):** Ubah cara memotong jika terlalu panjang
   - **Capitalization (Line 3320-3322):** Ubah logic capitalize

2. **`frontend-cofind/src/utils/reviewSummary.js`** (jika di-uncomment)
   - **Post-processing (Line 117-151):** Tambah cleaning logic di frontend

---

### **Skenario 6: Mengubah Data Source**

**File yang perlu diubah:**
1. **`app.py`** - Endpoint `/api/llm/summarize-review`
   - **File path (Line 3189):** Ubah path ke `reviews.json`
   - **Jumlah review (Line 3211):** Ubah dari 10 review
   - **Format reviews (Line 3214-3220):** Ubah cara format reviews untuk context

---

## 📋 Checklist Perubahan

Saat mengubah logic AI summary, pastikan untuk:

- [ ] **Backend (`app.py`):**
  - [ ] Ubah system prompt/user prompt sesuai kebutuhan
  - [ ] Sesuaikan model parameters (temperature, max_tokens, top_p)
  - [ ] Update post-processing logic
  - [ ] Update truncation logic jika mengubah panjang
  - [ ] Test endpoint dengan berbagai input

- [ ] **Frontend (`reviewSummary.js`):**
  - [ ] Update cache version jika format berubah
  - [ ] Sesuaikan post-processing jika ada
  - [ ] Test cache invalidation

- [ ] **Frontend (`CoffeeShopCard.jsx`):**
  - [ ] Pastikan endpoint yang dipanggil benar
  - [ ] Test display summary
  - [ ] Test error handling

- [ ] **Testing:**
  - [ ] Test dengan berbagai coffee shop
  - [ ] Test dengan review yang sedikit
  - [ ] Test dengan review yang banyak
  - [ ] Test error cases (LLM tidak tersedia, dll)

---

## 🎯 Ringkasan File Penting

| File | Lokasi | Fungsi Utama | Prioritas |
|------|--------|--------------|-----------|
| `app.py` | Line 805-1101 | Endpoint `/api/coffeeshops/<place_id>/summarize` | 🔴 **PENTING** |
| `app.py` | Line 3154-3363 | Endpoint `/api/llm/summarize-review` | 🔴 **PENTING** |
| `reviewSummary.js` | `frontend-cofind/src/utils/` | Fetch & cache summary | 🟡 **PENTING** |
| `CoffeeShopCard.jsx` | `frontend-cofind/src/components/` | Display summary | 🟢 **SEDANG** |
| `SmartReviewSummary.jsx` | `frontend-cofind/src/components/` | Component kosong (future) | 🔵 **RENDAH** |

---

## 💡 Tips

1. **Test perubahan di development environment dulu**
2. **Increment cache version** di `reviewSummary.js` jika format output berubah
3. **Monitor console logs** di backend untuk melihat output LLM
4. **Gunakan temperature rendah (0.1-0.4)** untuk hasil yang lebih konsisten
5. **Gunakan temperature tinggi (0.7-0.9)** jika ingin hasil yang lebih kreatif
6. **Pastikan post-processing** menghapus format yang tidak diinginkan
7. **Test dengan edge cases:** review kosong, review sangat panjang, dll

---

**Dokumentasi ini dibuat untuk membantu memahami file-file yang perlu diperhatikan saat mengubah logic AI summary.**
