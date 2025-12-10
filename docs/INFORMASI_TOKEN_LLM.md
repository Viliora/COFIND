# 📊 Informasi Penggunaan Token LLM dan Batasan Analisis

## 🎯 Ringkasan

Dokumen ini menjelaskan **total penggunaan token LLM** dalam menganalisa context dan **batasan maksimal** coffee shop serta review yang dapat dianalisa oleh LLM.

---

## 📈 Total Penggunaan Token LLM

### **Formula Perhitungan Token**

Sistem menggunakan estimasi: **1 token ≈ 4 karakter**

### **Komponen Token Input**

Token input LLM terdiri dari 3 komponen utama:

1. **Context Tokens** (Data Coffee Shop + Reviews)
   - Sumber: `places_context` dari file JSON lokal
   - Berisi: 20 coffee shops terbaik (sorted by rating & review count) dengan 2 reviews per shop
   - Estimasi: **~4,000 - 5,000 tokens**

2. **System Prompt Tokens**
   - Sumber: System prompt dengan aturan dan format output
   - Estimasi: **~1,500 - 2,000 tokens**

3. **User Prompt Tokens**
   - Sumber: Input user (kata kunci preferensi)
   - Estimasi: **~100 - 500 tokens** (tergantung panjang input)

### **Total Input Tokens**

```
Total Input Tokens = Context Tokens + System Tokens + User Tokens
                   ≈ 4,000 - 5,000 + 1,500 - 2,000 + 100 - 500
                   ≈ 5,600 - 7,500 tokens
```

### **Output Tokens**

- **Max Output Tokens**: `2,048 tokens`
- **Konfigurasi**: `max_tokens=2048` (optimal untuk maksimal 3 coffee shop rekomendasi)

### **Total Token Usage per Request**

```
Total Token Usage = Input Tokens + Output Tokens
                  ≈ 5,600 - 7,500 + 500 - 1,500 (actual output)
                  ≈ 6,100 - 9,000 tokens per request
```

### **Monitoring & Warning**

Sistem akan memberikan **warning** jika total input tokens melebihi **6,000 tokens**:

```python
if estimated_total_input_tokens > 6000:
    print(f"[WARNING] Input tokens sangat besar ({estimated_total_input_tokens} tokens). Mungkin exceed model limit!")
```

**Lokasi Kode**: `app.py` line 915-924

---

## 🔢 Batasan Maksimal Coffee Shop dan Review

### **1. Maksimal Coffee Shop**

**Konfigurasi Saat Ini**: **20 coffee shops terbaik**

**Lokasi Kode**: 
- `app.py` line 363: `def _fetch_coffeeshops_with_reviews_from_json(location_str, max_shops=20)`
- `app.py` line 771: `places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=20)`

**Alasan**: 
- 20 coffee shops terbaik (sorted by rating & review count) untuk kualitas rekomendasi
- Menjaga context size dalam batas aman model LLM
- Fokus pada coffee shop berkualitas tinggi
- Mengurangi token usage sambil tetap memberikan rekomendasi terbaik

### **2. Maksimal Review per Coffee Shop**

**Konfigurasi Saat Ini**: **2 reviews per coffee shop**

**Lokasi Kode**: `app.py` line 437
```python
for review in reviews[:2]:  # Max 2 reviews per coffee shop
```

**Alasan**:
- 2 reviews sudah cukup untuk bukti/evidence rekomendasi
- Mengurangi total reviews dari 60 → 40 (20 shops × 2 reviews)
- Mengoptimalkan penggunaan token
- Coffee shop sudah terpilih berdasarkan rating tinggi, jadi review lebih fokus

### **3. Maksimal Panjang Review**

**Konfigurasi Saat Ini**: **150 karakter per review**

**Lokasi Kode**: `app.py` line 444-445
```python
if len(review_text) > 150:
    review_text = review_text[:147] + "..."
```

**Alasan**:
- Review yang terlalu panjang tidak efisien untuk context
- 150 karakter sudah cukup untuk memberikan informasi relevan
- Mengurangi penggunaan token secara signifikan

### **4. Minimum Panjang Review**

**Konfigurasi**: **20 karakter minimum**

**Lokasi Kode**: `app.py` line 439
```python
if review_text and len(review_text) > 20:  # Min 20 karakter
```

**Alasan**: Filter review yang terlalu pendek atau tidak informatif

---

## 📊 Perhitungan Detail

### **Estimasi Context Size per Coffee Shop**

Setiap coffee shop dalam context berisi:
- Nama: ~20-50 karakter
- Rating: ~30 karakter
- Alamat: ~50-150 karakter
- Google Maps URL: ~80 karakter
- 2 reviews × 150 karakter: ~300 karakter
- Formatting & separator: ~50 karakter

**Total per shop**: ~530-660 karakter ≈ **130-165 tokens**

### **Total Context untuk 20 Coffee Shops Terbaik**

```
20 shops × 165 tokens = 3,300 tokens
Header & formatting = ~500 tokens
Total Context = ~3,800 tokens
```

### **Total Input dengan System & User Prompt**

```
Context:        ~3,800 tokens
System Prompt:   ~1,750 tokens
User Prompt:     ~300 tokens (rata-rata)
─────────────────────────────
Total Input:     ~5,850 tokens
```

### **Sorting Coffee Shops**

Coffee shops diurutkan berdasarkan:
1. **Rating** (descending) - Rating lebih tinggi lebih diprioritaskan
2. **Jumlah Review** (descending) - Jika rating sama, yang punya lebih banyak review diprioritaskan

Ini memastikan LLM menganalisis coffee shop terbaik untuk rekomendasi.

---

## ⚠️ Batasan Model LLM

### **Model yang Digunakan**

**Default**: `meta-llama/Llama-3.1-8B-Instruct`

**Context Window**: **8,192 tokens**

### **Rekomendasi Safe Limit**

- **Input Tokens**: < 6,000 tokens (75% dari limit)
- **Output Tokens**: < 2,048 tokens
- **Total**: < 8,048 tokens (98% dari limit)

### **Status Saat Ini**

```
Estimated Total Input: ~5,850 tokens
Model Limit:           8,192 tokens
Status:                ✅ AMAN (71% dari limit)
```

**Catatan**: Estimasi ini menggunakan formula kasar (1 token ≈ 4 karakter). Tokenizer aktual mungkin berbeda, sehingga bisa lebih aman atau lebih berisiko.

---

## 🔧 Konfigurasi yang Dapat Disesuaikan

### **Jika Ingin Mengurangi Token Usage**

**Option 1: Kurangi Jumlah Coffee Shop**
```python
# app.py line 771
places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=15)
# Mengurangi dari 20 → 15 shops
# Estimasi penghematan: ~800 tokens
```

**Option 2: Kurangi Review per Shop**
```python
# app.py line 437
for review in reviews[:1]:  # Dari 2 → 1 review
# Estimasi penghematan: ~1,000 tokens
```

**Option 3: Persingkat Review**
```python
# app.py line 444
if len(review_text) > 100:  # Dari 150 → 100 karakter
    review_text = review_text[:97] + "..."
# Estimasi penghematan: ~1,000 tokens
```

### **Jika Ingin Meningkatkan Data (Risky)**

**Option 1: Tambah Coffee Shop**
```python
# app.py line 771
places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=30)
# ⚠️ WARNING: Bisa exceed model limit!
```

**Option 2: Tambah Review per Shop**
```python
# app.py line 437
for review in reviews[:3]:  # Dari 2 → 3 reviews
# ⚠️ WARNING: Bisa exceed model limit!
```

---

## 📝 Logging & Monitoring

### **Console Log Output**

Sistem akan menampilkan estimasi token di console:

```
[LLM] Estimated input tokens - Context: 3800, System: 1750, User: 300, Total: 5850
```

**Lokasi**: `app.py` line 920

### **Context Length Logging**

```
[JSON+REVIEWS] Selected top 20 coffee shops (sorted by rating & review count), preparing context...
[JSON+REVIEWS] Context prepared: 20 shops with reviews, 15000 characters
```

**Lokasi**: `app.py` line 459

---

## 🎯 Kesimpulan

### **Konfigurasi Optimal Saat Ini**

| Parameter | Nilai | Alasan |
|-----------|-------|--------|
| Max Coffee Shops | 20 (terbaik) | Top 20 sorted by rating & review count |
| Max Reviews per Shop | 2 | Cukup untuk evidence, lebih efisien |
| Max Review Length | 150 chars | Informasi relevan tanpa boros |
| Min Review Length | 20 chars | Filter review tidak informatif |
| Max Output Tokens | 2,048 | Optimal untuk response |
| Max Rekomendasi | 3 coffee shop | Batasan output LLM |
| Sorting Method | Rating + Review Count | Memastikan coffee shop terbaik dianalisis |
| Review Source | reviews.json | Review ditampilkan persis dari JSON, bukan dari LLM |

### **Total Token Usage**

- **Input**: ~5,850 tokens (71% dari limit 8,192) ✅ AMAN
- **Output**: ~500-1,500 tokens (actual)
- **Total**: ~6,350-7,350 tokens per request

### **Rekomendasi**

1. ✅ **Gunakan 20 coffee shops terbaik** - sudah optimal dan aman
2. ✅ **Gunakan 2 reviews per shop** - sudah cukup dan efisien
3. ✅ **Sorting by rating & review count** - memastikan kualitas rekomendasi
4. ✅ **Token usage aman** - masih dalam batas aman model

---

## 📚 Referensi

- **File Kode**: `app.py` line 363-467, 734-963
- **Dokumentasi Optimasi**: `FIX_CONTEXT_TOO_LARGE_ERROR.md`
- **Model Info**: Hugging Face `meta-llama/Llama-3.1-8B-Instruct`

---

**Terakhir Diupdate**: 2024
**Versi**: 1.0
