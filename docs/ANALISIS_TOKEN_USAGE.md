# 📊 Analisis Penggunaan Token LLM pada Page Analyzer

## 🎯 Ringkasan

Dokumen ini menjelaskan **bagian mana yang menggunakan kuota token terbesar** dalam analisis LLM pada page analyzer.

---

## 📈 Breakdown Penggunaan Token

### **Total Input Tokens terdiri dari 3 komponen:**

```
Total Input Tokens = Context Tokens + System Prompt Tokens + User Prompt Tokens
```

---

## 🔴 1. CONTEXT TOKENS (PALING BESAR) - ~4,000-5,000 tokens

### **Apa yang dikirim:**
- **Data Coffee Shop**: 15 coffee shops terbaik (default: `max_shops=15`)
- **Reviews**: Maksimal 3 reviews per coffee shop
- **Format**: Nama, Rating, Google Maps URL, Reviews (maksimal 150 karakter per review)

### **Lokasi Kode:**
```python
# app.py line 860
places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=15, keywords=expanded_keywords_for_filter)
```

### **Perhitungan Detail:**
```
15 coffee shops × (
    Nama (~30 karakter) +
    Rating (~30 karakter) +
    Google Maps URL (~80 karakter) +
    3 reviews × 150 karakter +
    Formatting (~50 karakter)
) = ~15 × 640 karakter = ~9,600 karakter

Estimasi Token: 9,600 ÷ 4 = ~2,400 tokens (minimum)
Dengan header & formatting: ~4,000-5,000 tokens
```

### **Faktor yang Mempengaruhi:**
1. **Jumlah Coffee Shop** (`max_shops=15`)
   - Semakin banyak shop, semakin besar token usage
   - Setiap shop menambah ~250-350 tokens

2. **Jumlah Review per Shop** (max 3 reviews)
   - Setiap review menambah ~40-50 tokens (150 karakter ÷ 4)
   - 3 reviews = ~120-150 tokens per shop

3. **Panjang Review** (max 150 karakter)
   - Review di-truncate menjadi 150 karakter untuk menghemat token
   - Lokasi: `app.py` line 741-742

### **Cara Mengurangi:**
- Kurangi `max_shops` dari 15 → 10 (hemat ~1,200 tokens)
- Kurangi review dari 3 → 2 per shop (hemat ~450 tokens)
- Kurangi panjang review dari 150 → 100 karakter (hemat ~1,125 tokens)

---

## 🟡 2. SYSTEM PROMPT TOKENS - ~1,500-2,000 tokens

### **Apa yang dikirim:**
- Instruksi lengkap untuk LLM
- Aturan analisis mendalam
- Daftar atribut pilihan/kriteria coffee shop
- Format output yang wajib
- Contoh output yang benar dan salah
- Sinonim keywords yang relevan

### **Lokasi Kode:**
```python
# app.py line 867-975
system_prompt = f"""Anda adalah asisten rekomendasi coffee shop...
[DALAM INI: Semua instruksi, aturan, format, contoh]
"""
```

### **Perhitungan:**
```
System prompt length: ~6,000-8,000 karakter
Estimasi Token: 6,000-8,000 ÷ 4 = ~1,500-2,000 tokens
```

### **Faktor yang Mempengaruhi:**
- Panjang instruksi dan aturan
- Jumlah contoh yang diberikan
- Daftar sinonim yang lengkap

### **Cara Mengurangi:**
- Persingkat instruksi (tapi bisa mengurangi kualitas output)
- Kurangi contoh (tapi bisa mengurangi akurasi)
- **TIDAK DISARANKAN** karena bisa mengurangi kualitas analisis LLM

---

## 🟢 3. USER PROMPT TOKENS - ~100-500 tokens

### **Apa yang dikirim:**
- `filtered_user_text`: Input user setelah irrelevant keywords dihapus
- Instruksi spesifik untuk task (recommend/analyze/summarize)
- Daftar atribut pilihan yang relevan
- Contoh analisis

### **Lokasi Kode:**
```python
# app.py line 1181-1393 (untuk task='recommend')
user_content = f"""PREFERENSI SAYA (Natural Language):
"{filtered_user_text}"
[Instruksi dan contoh]
"""
```

### **Perhitungan:**
```
User prompt length: ~400-2,000 karakter (tergantung task)
Estimasi Token: 400-2,000 ÷ 4 = ~100-500 tokens
```

### **Faktor yang Mempengaruhi:**
- Panjang `filtered_user_text` (biasanya pendek, max 100 karakter)
- Task yang dipilih (recommend lebih panjang dari analyze)
- Jumlah contoh yang diberikan

---

## 📊 Total Token Usage

### **Estimasi per Request:**

```
Context Tokens:      ~4,000-5,000 tokens (60-70% dari total input)
System Prompt:       ~1,500-2,000 tokens (20-25% dari total input)
User Prompt:         ~100-500 tokens   (2-5% dari total input)
─────────────────────────────────────────────────────────
Total Input:         ~5,600-7,500 tokens

Output Tokens:       ~500-1,500 tokens (actual output)
─────────────────────────────────────────────────────────
Total Usage:         ~6,100-9,000 tokens per request
```

### **Model Limit:**
- **Context Window**: 8,192 tokens (Llama 3.1 8B)
- **Status Saat Ini**: ✅ AMAN (75-90% dari limit)

---

## 🔍 Bagian yang PALING BESAR: CONTEXT TOKENS

### **Mengapa Context Tokens Paling Besar?**

1. **15 Coffee Shops** × **3 Reviews** = **45 reviews total**
2. Setiap review = **150 karakter** = **~40 tokens**
3. **45 reviews** × **40 tokens** = **~1,800 tokens** (hanya dari reviews)
4. Ditambah nama, rating, URL per shop = **~2,200 tokens**
5. Ditambah formatting & header = **~4,000-5,000 tokens total**

### **Perbandingan:**

```
Context Tokens:      ████████████████████ 4,000-5,000 tokens (70%)
System Prompt:       ████████ 1,500-2,000 tokens (25%)
User Prompt:         ██ 100-500 tokens (5%)
```

---

## ⚠️ Warning & Monitoring

Sistem sudah memiliki monitoring untuk mendeteksi penggunaan token yang besar:

```python
# app.py line 1500-1508
if estimated_total_input_tokens + actual_max_tokens > 8192:
    print(f"[ERROR] Total usage MELEBIHI context window!")
elif estimated_total_input_tokens + actual_max_tokens > 7500:
    print(f"[WARNING] Total usage mendekati context window!")
elif estimated_total_input_tokens > 5000:
    print(f"[INFO] Input tokens cukup besar. Masih dalam batas aman.")
```

---

## 💡 Rekomendasi Optimasi

### **Jika Ingin Mengurangi Token Usage:**

1. **Kurangi Jumlah Coffee Shop** (PALING EFEKTIF)
   ```python
   # app.py line 860
   places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=10)  # Dari 15 → 10
   # Hemat: ~1,200 tokens
   ```

2. **Kurangi Review per Shop**
   ```python
   # app.py line 734
   for review in reviews[:2]:  # Dari 3 → 2 reviews
   # Hemat: ~450 tokens
   ```

3. **Persingkat Review**
   ```python
   # app.py line 741
   if len(review_text) > 100:  # Dari 150 → 100 karakter
   # Hemat: ~1,125 tokens
   ```

### **Trade-off:**
- Semakin sedikit data → Semakin sedikit token
- TAPI: Semakin sedikit data → Semakin kurang akurat rekomendasi
- **Rekomendasi**: Tetap gunakan 15 shops dengan 3 reviews (sudah optimal)

---

## 📝 Kesimpulan

**Bagian yang menggunakan kuota token terbesar:**
1. ✅ **CONTEXT TOKENS** (places_context) - **~4,000-5,000 tokens** (70%)
2. 🟡 **SYSTEM PROMPT** - **~1,500-2,000 tokens** (25%)
3. 🟢 **USER PROMPT** - **~100-500 tokens** (5%)

**Total: ~5,600-7,500 tokens per request**

**Status: ✅ AMAN** (masih dalam batas 8,192 tokens)

