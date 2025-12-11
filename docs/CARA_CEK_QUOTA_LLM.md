# 📊 Cara Mengecek Limit Quota Request LLM

Dokumen ini menjelaskan berbagai cara untuk mengecek quota dan limit untuk request LLM di aplikasi COFIND.

---

## 🎯 Ringkasan

Aplikasi COFIND menggunakan **Hugging Face Inference API** untuk LLM. Ada beberapa jenis quota/limit yang perlu dimonitor:

1. **Hugging Face API Quota** - Rate limit dan usage limit dari Hugging Face
2. **Token Usage Limit** - Batasan context window model LLM (8,192 tokens untuk Llama 3.1 8B)
3. **Google Places API Quota** - Quota untuk fetch data coffee shop (terkait dengan LLM context)

---

## 1️⃣ Mengecek Hugging Face API Quota

### **A. Melalui Hugging Face Website**

1. **Login ke Hugging Face:**
   - Buka: https://huggingface.co/
   - Login dengan akun yang memiliki `HF_API_TOKEN`

2. **Cek Usage & Quota:**
   - Buka: https://huggingface.co/settings/billing
   - Atau: https://huggingface.co/settings/tokens
   - Di sini Anda bisa melihat:
     - **API Usage** - Total request yang sudah digunakan
     - **Rate Limits** - Batasan request per menit/jam
     - **Quota Remaining** - Sisa quota yang tersedia
     - **Billing Information** - Informasi pembayaran jika menggunakan paid tier

3. **Cek Rate Limits:**
   - Free tier biasanya memiliki limit:
     - **30 requests per menit**
     - **1,000 requests per hari** (tergantung model)
   - Paid tier memiliki limit lebih tinggi

### **B. Melalui API Response**

Sistem akan otomatis mendeteksi error quota melalui response API:

```python
# Error yang muncul jika quota habis:
# - HTTP 402 (Payment Required)
# - HTTP 429 (Too Many Requests)
# - Error message: "exceeded", "credits", "quota"
```

**Lokasi Handling Error:**
- Backend: `app.py` - Endpoint `/api/llm/analyze` dan `/api/llm/summarize-review`
- Frontend: `frontend-cofind/src/utils/reviewSummary.js` (line 69-84)

### **C. Melalui Console Log Backend**

Saat request LLM gagal karena quota, backend akan menampilkan error:

```bash
# Jalankan backend dan lihat console output
python app.py

# Error yang muncul:
# [ERROR] HF API Error: 402 Payment Required
# [ERROR] HF API Error: 429 Too Many Requests
# [ERROR] Quota exceeded atau credits habis
```

---

## 2️⃣ Mengecek Token Usage (Context Window Limit)

### **A. Melalui Console Log Backend**

Sistem otomatis menghitung dan menampilkan estimasi token usage di console:

**Lokasi Kode:** `app.py` line 1140-1190

**Output Console:**
```
[LLM] Estimated input tokens - Context: 3800, System: 1750, User: 300, Total: 5850
[LLM] ========== TOKEN BREAKDOWN ==========
[LLM] INPUT TOKENS (yang dikirim ke LLM):
  - Context data (coffee shops + reviews): ~3800 tokens
  - System prompt (aturan & format): ~1750 tokens
  - User prompt (kata kunci user): ~300 tokens
[LLM] TOTAL INPUT: ~5850 tokens
[LLM] MODEL LIMIT: 8192 tokens (Llama 3.1 8B)
[LLM] AVAILABLE FOR OUTPUT: ~2342 tokens
[LLM] REQUESTED OUTPUT: 3072 tokens
[LLM] ACTUAL MAX OUTPUT: 2342 tokens (adjusted)
[LLM] STATUS: ✅ WITHIN LIMIT (71% dari limit)
```

### **B. Warning & Error Messages**

Sistem akan memberikan warning jika mendekati limit:

**Warning Level 1** (Input besar tapi masih aman):
```
[WARNING] Input besar, mengurangi max_tokens dari 3072 ke 2342
[WARNING] ⚠️ PERINGATAN: max_tokens (2342) mungkin tidak cukup untuk output lengkap dengan review!
```

**Warning Level 2** (Sangat kritis):
```
[ERROR] Input terlalu besar! Hanya 512 tokens tersedia untuk output.
[ERROR] Output akan sangat terbatas atau request mungkin gagal!
[ERROR] ⚠️ PERINGATAN: max_tokens (256) terlalu kecil untuk output lengkap dengan review!
```

### **C. Batasan Model**

**Model yang Digunakan:** `meta-llama/Llama-3.1-8B-Instruct`

| Parameter | Nilai | Keterangan |
|-----------|-------|------------|
| Context Window | 8,192 tokens | Total maksimal (input + output) |
| Recommended Max Input | < 6,000 tokens | 75% dari limit untuk safety |
| Max Output Tokens | 3,072 tokens | Request maksimal (akan disesuaikan jika input besar) |
| Current Usage | ~5,850 tokens | 71% dari limit ✅ AMAN |

**Dokumentasi Lengkap:** `docs/INFORMASI_TOKEN_LLM.md`

---

## 3️⃣ Monitoring Real-time di Aplikasi

### **A. Browser Console (Frontend)**

Buka Developer Tools (F12) dan lihat Console tab:

**Error Quota Exceeded:**
```javascript
[ReviewSummary] LLM service unavailable (quota exceeded). 
Review summaries will be disabled. 
Clear localStorage to re-enable.
```

**Lokasi:** `frontend-cofind/src/utils/reviewSummary.js` line 82

### **B. Backend Log File**

Backend menulis log ke file:

**Lokasi Log:**
- `logs/flask_server.log` - Log server utama
- `logs/flask_debug.log` - Log debug mode

**Cara Cek:**
```powershell
# Windows PowerShell
Get-Content logs/flask_server.log -Tail 50

# Atau buka file langsung
notepad logs/flask_server.log
```

**Cari Keyword:**
- `[LLM]` - Log terkait LLM
- `[ERROR]` - Error termasuk quota exceeded
- `[WARNING]` - Warning terkait token limit
- `quota` - Error quota
- `exceeded` - Limit exceeded

---

## 4️⃣ Cara Mengecek Google Places API Quota

Google Places API juga digunakan untuk fetch data coffee shop yang menjadi context LLM.

### **A. Melalui Google Cloud Console**

1. **Buka Google Cloud Console:**
   - https://console.cloud.google.com/

2. **Navigasi ke API & Services:**
   - APIs & Services → Dashboard
   - Atau: APIs & Services → Quotas

3. **Cek Quota:**
   - Pilih "Places API"
   - Lihat "Quotas" tab
   - Cek:
     - **Requests per day** - Total request per hari
     - **Requests per minute** - Rate limit per menit
     - **Current usage** - Penggunaan saat ini

### **B. Melalui Backend Log**

Sistem akan menampilkan jumlah API calls:

```
[LLM] Fetching coffee shops WITH REVIEWS from local JSON files
[LLM] Total API calls: 33 (3 Text Search + 30 Place Details)
```

**Dokumentasi:** `docs/UPDATE_60_COFFEE_SHOPS.md` (line 209-230)

---

## 5️⃣ Script untuk Monitoring Otomatis

### **A. Cek Token Usage dari Log**

Buat script Python untuk parse log dan cek token usage:

```python
# scripts/check_llm_quota.py
import re
import os

def check_token_usage_from_log():
    log_file = "logs/flask_server.log"
    if not os.path.exists(log_file):
        print("Log file tidak ditemukan")
        return
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Cari baris terakhir dengan token info
    for line in reversed(lines):
        if "[LLM] TOTAL INPUT:" in line:
            print("Token Usage Terakhir:")
            print(line.strip())
            # Extract angka
            match = re.search(r'~(\d+) tokens', line)
            if match:
                tokens = int(match.group(1))
                limit = 8192
                percentage = (tokens / limit) * 100
                print(f"Usage: {tokens}/{limit} tokens ({percentage:.1f}%)")
                if percentage > 90:
                    print("⚠️ WARNING: Mendekati limit!")
                elif percentage > 75:
                    print("⚠️ CAUTION: Di atas 75% limit")
                else:
                    print("✅ AMAN")
            break

if __name__ == "__main__":
    check_token_usage_from_log()
```

**Cara Pakai:**
```powershell
python scripts/check_llm_quota.py
```

### **B. Cek Error Quota dari Log**

```python
# scripts/check_quota_errors.py
import os

def check_quota_errors():
    log_file = "logs/flask_server.log"
    if not os.path.exists(log_file):
        print("Log file tidak ditemukan")
        return
    
    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    errors = []
    for i, line in enumerate(lines[-100:], 1):  # Cek 100 baris terakhir
        if any(keyword in line.lower() for keyword in ['quota', 'exceeded', '402', '429', 'payment required']):
            errors.append((i, line.strip()))
    
    if errors:
        print(f"⚠️ Ditemukan {len(errors)} error terkait quota:")
        for line_num, error in errors[-5:]:  # Tampilkan 5 terakhir
            print(f"  Line {line_num}: {error}")
    else:
        print("✅ Tidak ada error quota ditemukan")

if __name__ == "__main__":
    check_quota_errors()
```

---

## 6️⃣ Troubleshooting Quota Issues

### **Problem 1: Quota Exceeded (HF API)**

**Gejala:**
- Error 402 atau 429 dari Hugging Face API
- Frontend menampilkan: "LLM service unavailable (quota exceeded)"

**Solusi:**
1. **Cek Hugging Face Dashboard:**
   - Login ke https://huggingface.co/settings/billing
   - Lihat sisa quota
   - Upgrade ke paid tier jika perlu

2. **Implementasi Retry Logic:**
   - Tambahkan delay antar request
   - Implement exponential backoff

3. **Reduce Request Frequency:**
   - Cache response LLM
   - Kurangi jumlah request yang tidak perlu

### **Problem 2: Token Limit Exceeded**

**Gejala:**
- Error: "Input terlalu besar! Hanya X tokens tersedia untuk output"
- Response terpotong atau tidak lengkap

**Solusi:**
1. **Kurangi Jumlah Coffee Shop:**
   ```python
   # app.py line 769
   places_context = _fetch_coffeeshops_with_reviews_from_json(location, max_shops=15)
   # Ubah dari 15 ke 10 atau 12
   ```

2. **Kurangi Review per Shop:**
   ```python
   # app.py line 437
   for review in reviews[:1]:  # Dari 2 ke 1 review
   ```

3. **Persingkat Review:**
   ```python
   # app.py line 444
   if len(review_text) > 100:  # Dari 150 ke 100 karakter
   ```

**Dokumentasi:** `docs/FIX_CONTEXT_TOO_LARGE_ERROR.md`

### **Problem 3: Google Places API Quota**

**Gejala:**
- Error dari Google Places API
- Coffee shop data tidak ter-load

**Solusi:**
1. **Cek Google Cloud Console:**
   - https://console.cloud.google.com/apis/dashboard
   - Lihat quota usage

2. **Kurangi API Calls:**
   ```python
   # Kurangi max_shops untuk mengurangi API calls
   places_context = _fetch_coffeeshops_with_reviews_context(location, max_shops=20)
   ```

---

## 7️⃣ Best Practices

### **✅ Monitoring Rutin**

1. **Cek Log Harian:**
   - Review `logs/flask_server.log` setiap hari
   - Cari warning atau error terkait quota

2. **Monitor Token Usage:**
   - Pastikan token usage < 75% dari limit (6,000 tokens)
   - Jika > 75%, pertimbangkan optimasi

3. **Cek HF API Usage:**
   - Login ke Hugging Face dashboard mingguan
   - Monitor rate limit dan daily quota

### **✅ Optimasi Usage**

1. **Cache Response:**
   - Cache hasil LLM untuk query yang sama
   - Kurangi duplicate requests

2. **Optimasi Context:**
   - Gunakan hanya data yang relevan
   - Filter coffee shop sebelum kirim ke LLM

3. **Rate Limiting:**
   - Implement rate limiting di frontend
   - Prevent spam requests

---

## 8️⃣ Quick Reference

### **Command untuk Cek Quota:**

```powershell
# 1. Cek log backend (token usage)
Get-Content logs/flask_server.log -Tail 100 | Select-String "LLM"

# 2. Cek error quota
Get-Content logs/flask_server.log -Tail 100 | Select-String "quota|exceeded|402|429"

# 3. Cek token breakdown
Get-Content logs/flask_server.log -Tail 50 | Select-String "TOKEN BREAKDOWN"

# 4. Run monitoring script (jika sudah dibuat)
python scripts/check_llm_quota.py
```

### **URL Penting:**

- **Hugging Face Settings:** https://huggingface.co/settings/billing
- **Hugging Face Tokens:** https://huggingface.co/settings/tokens
- **Google Cloud Console:** https://console.cloud.google.com/apis/dashboard

### **File Dokumentasi Terkait:**

- `docs/INFORMASI_TOKEN_LLM.md` - Detail token usage
- `docs/LLM_SETUP_SUMMARY.md` - Setup LLM dan rate limits
- `docs/FIX_CONTEXT_TOO_LARGE_ERROR.md` - Fix token limit issues
- `docs/UPDATE_60_COFFEE_SHOPS.md` - Google Places API quota info

---

## 📝 Kesimpulan

Untuk mengecek quota LLM, Anda bisa:

1. ✅ **Hugging Face Dashboard** - Cek API usage dan rate limits
2. ✅ **Backend Console Log** - Monitor token usage real-time
3. ✅ **Log Files** - Review error dan warning dari log
4. ✅ **Browser Console** - Cek error di frontend
5. ✅ **Google Cloud Console** - Monitor Google Places API quota

**Monitoring rutin** adalah kunci untuk menghindari quota issues dan memastikan aplikasi berjalan lancar.

---

**Terakhir Diupdate:** 2024  
**Versi:** 1.0

