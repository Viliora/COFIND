# 🔄 Mengganti Akun HuggingFace - Dampak terhadap Project

Dokumen ini menjelaskan apakah mengganti akun HuggingFace untuk mendapatkan free trial usage token lagi akan berpengaruh terhadap project COFIND.

---

## ✅ **JAWABAN SINGKAT: TIDAK BERPENGARUH (dengan syarat)**

**Mengganti akun HuggingFace TIDAK akan berpengaruh** terhadap project, **ASALKAN** Anda:
1. ✅ Update `HF_API_TOKEN` dengan token baru
2. ✅ Token baru memiliki akses ke model yang sama
3. ✅ Restart aplikasi setelah update token

---

## 🔍 **Bagaimana HF_API_TOKEN Digunakan di Project?**

### **Di `app.py`:**

```22:30:app.py
HF_API_TOKEN = os.getenv('HF_API_TOKEN')  # Pastikan diset di environment (.env)
HF_MODEL = os.getenv('HF_MODEL', "meta-llama/Llama-3.1-8B-Instruct")  # default model

# Initialize Hugging Face Inference Client (optional)
hf_client = None
if HF_API_TOKEN:
    hf_client = InferenceClient(api_key=HF_API_TOKEN)
else:
    print("[WARNING] HF_API_TOKEN tidak diset. Endpoint LLM akan nonaktif.")
```

**Penjelasan:**
- ✅ Token dibaca dari **environment variable** (`HF_API_TOKEN`)
- ✅ **Tidak hardcode** di code
- ✅ Hanya digunakan untuk **initialize InferenceClient**
- ✅ **Tidak ada dependency** terhadap akun tertentu

**Kesimpulan:** Project hanya perlu **token yang valid**, tidak peduli dari akun mana token tersebut berasal.

---

## 🔄 **Cara Mengganti Akun HuggingFace**

### **Step 1: Buat Akun Baru HuggingFace**

1. **Sign up akun baru:**
   - Buka: https://huggingface.co/join
   - Buat akun dengan email baru
   - Verifikasi email

2. **Generate API Token:**
   - Login ke akun baru
   - Buka: https://huggingface.co/settings/tokens
   - Klik "New token"
   - Pilih scope: **Read** (cukup untuk Inference API)
   - Copy token (format: `hf_...`)

### **Step 2: Update Token di Project**

#### **A. Development (Local)**

**Update `.env` file:**
```env
# Token lama (hapus atau comment)
# HF_API_TOKEN=hf_old_token_here

# Token baru
HF_API_TOKEN=hf_new_token_here
```

**Restart backend:**
```powershell
# Stop backend (Ctrl+C)
# Start lagi
python app.py
```

#### **B. Production (Deployment Platform)**

**Railway:**
1. Buka Railway dashboard
2. Pilih project → Settings → Variables
3. Edit `HF_API_TOKEN`
4. Set value dengan token baru
5. Save (auto-restart)

**Render:**
1. Buka Render dashboard
2. Pilih service → Environment
3. Edit `HF_API_TOKEN`
4. Set value dengan token baru
5. Save (auto-restart)

**Heroku:**
```bash
heroku config:set HF_API_TOKEN=hf_new_token_here
# Auto-restart setelah set
```

### **Step 3: Verifikasi**

**Test endpoint:**
```bash
# Test LLM endpoint
curl -X POST http://localhost:5000/api/llm/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'
```

**Cek log:**
- ✅ Tidak ada error "HF_API_TOKEN tidak dikonfigurasi"
- ✅ Tidak ada error 401 (Unauthorized)
- ✅ Response berhasil

---

## ⚠️ **Konsekuensi & Peringatan**

### **1. Terms of Service (ToS) HuggingFace**

⚠️ **PENTING:** Membuat multiple akun untuk "reset" quota bisa melanggar Terms of Service HuggingFace.

**Risiko:**
- ❌ Akun bisa di-ban
- ❌ Token bisa di-revoke
- ❌ Tidak etis

**Rekomendasi:**
- ✅ Gunakan akun sesuai ToS
- ✅ Pertimbangkan upgrade ke paid tier jika quota habis
- ✅ Optimize usage (caching, reduce requests)

### **2. Data & History**

**Yang TIDAK hilang:**
- ✅ Code project (tetap sama)
- ✅ Data coffee shop (tetap sama)
- ✅ Konfigurasi aplikasi (tetap sama)

**Yang berubah:**
- ⚠️ Token berbeda (harus update)
- ⚠️ Quota reset (dari akun baru)
- ⚠️ History usage di dashboard berbeda

### **3. Model Access**

**Penting:** Pastikan model yang digunakan **public** dan **accessible** untuk semua akun.

**Model yang digunakan:**
- `meta-llama/Llama-3.1-8B-Instruct` - ✅ Public, accessible untuk semua

**Jika model private:**
- ⚠️ Perlu akses khusus
- ⚠️ Token baru mungkin tidak punya akses
- ⚠️ Aplikasi akan error

---

## 💡 **Alternatif Solusi (Lebih Baik)**

### **1. Optimize Usage**

**Implement Caching:**
```python
# Cache LLM response untuk query yang sama
from functools import lru_cache
import hashlib

@lru_cache(maxsize=100)
def get_cached_llm_response(query_hash):
    # Call HuggingFace API
    pass
```

**Reduce Requests:**
- Cache response untuk query yang sama
- Batch multiple requests jika mungkin
- Reduce context size jika tidak perlu

### **2. Upgrade ke Paid Tier**

**Keuntungan:**
- ✅ Quota lebih besar
- ✅ Rate limit lebih tinggi
- ✅ Priority processing
- ✅ SLA guarantee
- ✅ Support lebih baik

**Harga:** Mulai dari ~$9/bulan

### **3. Gunakan Model Alternatif**

**Model yang lebih kecil (lebih murah):**
- `meta-llama/Llama-2-7b-chat-hf` - Lebih kecil, lebih cepat
- `google/flan-t5-large` - Model lebih kecil untuk task sederhana

**Ubah model:**
```env
HF_MODEL=meta-llama/Llama-2-7b-chat-hf
```

### **4. Monitor & Manage Quota**

**Cek quota rutin:**
- https://huggingface.co/settings/billing
- Monitor usage harian
- Set alert jika mendekati limit

**Implement rate limiting:**
- Limit request per user
- Queue system untuk request
- Graceful degradation jika quota habis

---

## 🔧 **Troubleshooting**

### **Problem 1: Token tidak bekerja**

**Gejala:** Error 401 (Unauthorized)

**Solusi:**
1. Cek token sudah benar (copy-paste lengkap)
2. Cek token belum expired
3. Cek token memiliki scope yang benar (Read)
4. Cek akun belum di-ban

### **Problem 2: Model tidak accessible**

**Gejala:** Error 403 (Forbidden) atau model not found

**Solusi:**
1. Cek model name sudah benar
2. Cek model public (bukan private)
3. Cek token memiliki akses ke model

### **Problem 3: Quota masih habis**

**Gejala:** Error 402 (Payment Required) atau 429 (Too Many Requests)

**Solusi:**
1. Cek quota di dashboard akun baru
2. Pastikan akun baru punya free tier quota
3. Tunggu reset quota (biasanya per hari)

---

## 📊 **Checklist Mengganti Akun**

### **Sebelum:**
- [ ] Backup token lama (jika perlu)
- [ ] Cek akun baru sudah dibuat
- [ ] Cek token baru sudah di-generate
- [ ] Cek model accessible dengan token baru

### **Saat Mengganti:**
- [ ] Update `.env` (development)
- [ ] Update environment variables (production)
- [ ] Restart aplikasi
- [ ] Test endpoint

### **Setelah:**
- [ ] Verifikasi endpoint berfungsi
- [ ] Cek log tidak ada error
- [ ] Test dengan beberapa request
- [ ] Monitor quota usage

---

## ✅ **Kesimpulan**

### **Apakah Berpengaruh?**
**TIDAK**, asalkan:
1. ✅ Update `HF_API_TOKEN` dengan token baru
2. ✅ Restart aplikasi
3. ✅ Token valid dan memiliki akses ke model

### **Rekomendasi:**
1. ⚠️ **Hindari** membuat multiple akun untuk "reset" quota (melanggar ToS)
2. ✅ **Optimize usage** dengan caching dan reduce requests
3. ✅ **Pertimbangkan** upgrade ke paid tier jika traffic tinggi
4. ✅ **Monitor quota** secara rutin

### **Best Practice:**
- ✅ Gunakan akun sesuai Terms of Service
- ✅ Optimize aplikasi untuk reduce API calls
- ✅ Implement caching untuk duplicate requests
- ✅ Monitor usage dan set budget limit

---

**Terakhir Diupdate:** 2024  
**Versi:** 1.0

