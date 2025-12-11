# 🚀 Panduan Deployment Project dengan HuggingFace LLM

Dokumen ini menjelaskan apakah project COFIND bisa di-deploy dengan menggunakan LLM open source dari HuggingFace, dan informasi penting yang perlu diketahui sebelum deployment.

---

## ✅ **JAWABAN SINGKAT: BISA DI-DEPLOY!**

**Ya, project ini BISA di-deploy** karena menggunakan **HuggingFace Inference API** yang merupakan **cloud-based service**. Anda **TIDAK PERLU**:
- ❌ GPU lokal
- ❌ Server dengan spesifikasi tinggi
- ❌ Install model LLM secara lokal
- ❌ Setup infrastructure khusus untuk ML

**Yang Anda PERLU:**
- ✅ API Token dari HuggingFace (gratis atau paid)
- ✅ Backend server (Flask) yang bisa akses internet
- ✅ Environment variables untuk API keys

---

## 🎯 **Cara Kerja HuggingFace Inference API**

### **Arsitektur:**

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Frontend  │ ───> │ Flask Backend│ ───> │ HuggingFace API │
│  (React)    │      │  (app.py)    │      │  (Cloud-based)  │
└─────────────┘      └──────────────┘      └─────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │ Google Places│
                    │     API      │
                    └──────────────┘
```

**Penjelasan:**
1. **Frontend** mengirim request ke **Flask Backend**
2. **Flask Backend** memanggil **HuggingFace Inference API** (cloud)
3. HuggingFace memproses request di server mereka (bukan di server Anda)
4. Response dikembalikan ke backend, lalu ke frontend

**Kesimpulan:** Backend Anda hanya perlu **koneksi internet** untuk memanggil API, tidak perlu menjalankan model LLM secara lokal.

---

## 📋 **Informasi Penting Sebelum Deployment**

### **1. HuggingFace API Token & Quota**

#### **A. Free Tier (Gratis)**
- ✅ **Tersedia untuk semua user**
- ⚠️ **Rate Limits:**
  - ~30 requests per menit
  - ~1,000 requests per hari (tergantung model)
- ⚠️ **Keterbatasan:**
  - Bisa habis quota jika traffic tinggi
  - Response time bisa lebih lambat
  - Tidak ada SLA (Service Level Agreement)

#### **B. Paid Tier (Berbayar)**
- 💰 **Mulai dari ~$9/bulan** (tergantung usage)
- ✅ **Rate Limits Lebih Tinggi:**
  - 100+ requests per menit
  - Unlimited requests per hari (dengan quota)
- ✅ **Keuntungan:**
  - Priority processing
  - SLA guarantee
  - Support lebih baik

**Rekomendasi:**
- **Development/Testing:** Gunakan Free Tier
- **Production dengan traffic rendah:** Free Tier bisa cukup
- **Production dengan traffic tinggi:** Pertimbangkan Paid Tier

**Cek Quota:** https://huggingface.co/settings/billing

### **2. Model yang Digunakan**

**Model Default:** `meta-llama/Llama-3.1-8B-Instruct`

| Parameter | Nilai | Keterangan |
|-----------|-------|------------|
| Context Window | 8,192 tokens | Batas maksimal input + output |
| Recommended Input | < 6,000 tokens | 75% dari limit untuk safety |
| Current Usage | ~5,850 tokens | 71% dari limit ✅ AMAN |
| Model Size | 8B parameters | Dijalankan di cloud HuggingFace |

**Alternatif Model (jika perlu):**
- `meta-llama/Llama-2-7b-chat-hf` - Model lebih kecil, lebih cepat
- `mistralai/Mistral-7B-Instruct-v0.2` - Alternatif open source
- `google/flan-t5-large` - Model lebih kecil untuk task sederhana

**Ubah Model:** Set `HF_MODEL` di environment variable

### **3. Environment Variables yang Diperlukan**

**Backend (`.env` di root project):**
```env
# Google Places API (wajib)
GOOGLE_PLACES_API_KEY=AIzaSy...

# HuggingFace API Token (wajib untuk LLM)
HF_API_TOKEN=hf_...

# Model LLM (opsional, default: meta-llama/Llama-3.1-8B-Instruct)
HF_MODEL=meta-llama/Llama-3.1-8B-Instruct
```

**Frontend (`.env` di `frontend-cofind/`):**
```env
# Backend API URL
VITE_API_BASE=https://your-backend-domain.com
```

**⚠️ PENTING:**
- Jangan commit `.env` ke Git
- Gunakan environment variables di platform deployment
- Jangan hardcode API keys di code

### **4. Dependencies yang Diperlukan**

**Backend (`requirements.txt`):**
```txt
Flask>=2.0
flask-cors>=3.0
python-dotenv>=0.21
requests>=2.0
huggingface-hub>=0.20.0  # Wajib untuk LLM
```

**Frontend (`package.json`):**
- Tidak ada dependency khusus untuk LLM (semua via backend API)

---

## 🌐 **Platform Deployment Options**

### **1. Backend Deployment**

#### **A. Railway** (Recommended untuk Backend)
- ✅ **Mudah setup** - Connect GitHub repo langsung
- ✅ **Auto-deploy** dari Git push
- ✅ **Environment variables** mudah dikonfigurasi
- ✅ **Free tier** tersedia (dengan limit)
- 💰 **Paid:** Mulai dari $5/bulan

**Setup:**
1. Sign up di https://railway.app
2. Connect GitHub repo
3. Set environment variables:
   - `GOOGLE_PLACES_API_KEY`
   - `HF_API_TOKEN`
   - `HF_MODEL` (opsional)
4. Deploy!

**Dokumentasi:** https://docs.railway.app

#### **B. Render**
- ✅ **Free tier** tersedia
- ✅ **Auto-deploy** dari Git
- ⚠️ **Free tier** sleep setelah 15 menit tidak aktif

**Setup:**
1. Sign up di https://render.com
2. Create new Web Service
3. Connect GitHub repo
4. Set environment variables
5. Deploy!

**Dokumentasi:** https://render.com/docs

#### **C. Heroku**
- ✅ **Mature platform**
- ⚠️ **Tidak ada free tier** lagi (mulai dari $7/bulan)
- ✅ **Add-ons** banyak tersedia

**Setup:**
1. Install Heroku CLI
2. `heroku create your-app-name`
3. `heroku config:set GOOGLE_PLACES_API_KEY=...`
4. `heroku config:set HF_API_TOKEN=...`
5. `git push heroku main`

**Dokumentasi:** https://devcenter.heroku.com

#### **D. DigitalOcean App Platform**
- ✅ **Simple pricing**
- ✅ **Auto-scaling**
- 💰 Mulai dari $5/bulan

#### **E. VPS (Self-hosted)**
- ✅ **Full control**
- ⚠️ **Perlu setup sendiri** (Nginx, Gunicorn, dll)
- 💰 Biaya VPS mulai dari $5/bulan

**Setup dengan Gunicorn:**
```bash
# Install Gunicorn
pip install gunicorn

# Run dengan Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### **2. Frontend Deployment**

#### **A. Vercel** (Recommended untuk Frontend)
- ✅ **Free tier** sangat baik
- ✅ **Auto-deploy** dari Git
- ✅ **CDN global** untuk performa cepat
- ✅ **HTTPS** otomatis

**Setup:**
1. Sign up di https://vercel.com
2. Import GitHub repo
3. Set build command: `npm run build`
4. Set output directory: `dist`
5. Set environment variables:
   - `VITE_API_BASE=https://your-backend-url.com`
6. Deploy!

**Dokumentasi:** https://vercel.com/docs

#### **B. Netlify**
- ✅ **Free tier** tersedia
- ✅ **Auto-deploy** dari Git
- ✅ **Form handling** built-in

**Setup:**
1. Sign up di https://netlify.com
2. Connect GitHub repo
3. Set build settings:
   - Build command: `npm run build`
   - Publish directory: `dist`
4. Set environment variables
5. Deploy!

**Dokumentasi:** https://docs.netlify.com

#### **C. GitHub Pages**
- ✅ **Gratis** untuk public repo
- ⚠️ **Static hosting only** (perlu setup khusus untuk SPA)
- ⚠️ **Tidak support environment variables** (perlu build script)

---

## 🔧 **Checklist Deployment**

### **Pre-Deployment:**

- [ ] **Environment Variables:**
  - [ ] `GOOGLE_PLACES_API_KEY` sudah diset
  - [ ] `HF_API_TOKEN` sudah diset
  - [ ] `HF_MODEL` sudah diset (atau gunakan default)
  - [ ] Frontend `VITE_API_BASE` sudah diset ke backend URL

- [ ] **Dependencies:**
  - [ ] `requirements.txt` sudah include `huggingface-hub`
  - [ ] `package.json` dependencies sudah lengkap

- [ ] **Security:**
  - [ ] `.env` sudah di-ignore di `.gitignore`
  - [ ] API keys tidak hardcode di code
  - [ ] CORS sudah dikonfigurasi dengan benar

- [ ] **Testing:**
  - [ ] Test LLM endpoint di localhost
  - [ ] Test dengan berbagai input
  - [ ] Test error handling (quota exceeded, dll)

### **Deployment Steps:**

1. **Deploy Backend:**
   ```bash
   # 1. Push code ke GitHub
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   
   # 2. Setup di platform (Railway/Render/Heroku)
   # - Connect GitHub repo
   # - Set environment variables
   # - Deploy!
   ```

2. **Deploy Frontend:**
   ```bash
   # 1. Update VITE_API_BASE di .env
   # 2. Build production
   cd frontend-cofind
   npm run build
   
   # 3. Deploy dist/ ke Vercel/Netlify
   ```

3. **Verify:**
   - [ ] Backend accessible di production URL
   - [ ] Frontend bisa connect ke backend
   - [ ] LLM endpoint berfungsi
   - [ ] Google Places API berfungsi

---

## ⚠️ **Peringatan & Best Practices**

### **1. Rate Limiting & Quota**

**Problem:** Free tier HuggingFace punya rate limit yang bisa habis.

**Solusi:**
- ✅ **Implement caching** untuk response LLM yang sama
- ✅ **Add retry logic** dengan exponential backoff
- ✅ **Monitor quota** secara rutin
- ✅ **Consider paid tier** jika traffic tinggi

**Contoh Caching:**
```python
# Cache LLM response untuk query yang sama
from functools import lru_cache
import hashlib

@lru_cache(maxsize=100)
def get_cached_llm_response(query_hash):
    # Call HuggingFace API
    pass
```

### **2. Error Handling**

**Wajib handle error berikut:**
- `402 Payment Required` - Quota habis
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - HuggingFace service error
- `Timeout` - Request terlalu lama

**Contoh Error Handling:**
```python
try:
    response = hf_client.chat.completions.create(...)
except Exception as e:
    if "402" in str(e) or "quota" in str(e).lower():
        return jsonify({
            'status': 'error',
            'message': 'LLM quota exceeded. Please try again later.'
        }), 503
    # Handle other errors...
```

### **3. Security**

- ✅ **Jangan expose API keys** di frontend
- ✅ **Gunakan HTTPS** di production
- ✅ **Set CORS** dengan domain spesifik (bukan `*`)
- ✅ **Rate limit** di backend untuk prevent abuse

**CORS Production:**
```python
# app.py
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://your-frontend-domain.com"]
    }
})
```

### **4. Monitoring**

**Setup monitoring untuk:**
- ✅ API response time
- ✅ Error rate
- ✅ Quota usage
- ✅ Request count

**Tools:**
- **Sentry** - Error tracking
- **LogRocket** - User session replay
- **Uptime Robot** - Uptime monitoring
- **Custom logging** - Log ke file atau service

---

## 💰 **Estimasi Biaya**

### **Development/Testing:**
- **HuggingFace:** Gratis (Free tier)
- **Google Places API:** $200 credit gratis, lalu pay-as-you-go
- **Hosting:** Gratis (Vercel free tier + Railway free tier)
- **Total:** **$0/bulan** (dengan limit)

### **Production (Traffic Rendah):**
- **HuggingFace:** Gratis atau $9/bulan (paid tier)
- **Google Places API:** ~$10-50/bulan (tergantung usage)
- **Backend Hosting:** $5-10/bulan (Railway/Render)
- **Frontend Hosting:** Gratis (Vercel)
- **Total:** **~$15-70/bulan**

### **Production (Traffic Tinggi):**
- **HuggingFace:** $20-100/bulan (tergantung usage)
- **Google Places API:** $50-200/bulan
- **Backend Hosting:** $20-50/bulan (dengan scaling)
- **Frontend Hosting:** Gratis atau $20/bulan (Pro)
- **Total:** **~$90-370/bulan**

---

## 🔍 **Troubleshooting Deployment**

### **Problem 1: LLM Endpoint Tidak Berfungsi**

**Gejala:** Error 503 atau "HF_API_TOKEN tidak dikonfigurasi"

**Solusi:**
1. Cek environment variable `HF_API_TOKEN` sudah diset di platform
2. Restart service setelah set environment variable
3. Cek log untuk error detail

### **Problem 2: Quota Exceeded**

**Gejala:** Error 402 atau 429 dari HuggingFace

**Solusi:**
1. Cek quota di https://huggingface.co/settings/billing
2. Upgrade ke paid tier jika perlu
3. Implement caching untuk reduce API calls

### **Problem 3: CORS Error**

**Gejala:** Frontend tidak bisa akses backend API

**Solusi:**
1. Update CORS di backend dengan frontend domain
2. Pastikan backend URL benar di frontend `.env`
3. Cek browser console untuk error detail

### **Problem 4: Timeout**

**Gejala:** Request LLM timeout setelah 30 detik

**Solusi:**
1. Increase timeout di platform (jika bisa)
2. Optimize context size (kurangi coffee shops)
3. Consider menggunakan model yang lebih kecil

---

## 📚 **Referensi & Dokumentasi**

### **HuggingFace:**
- **Inference API Docs:** https://huggingface.co/docs/api-inference
- **Pricing:** https://huggingface.co/pricing
- **Rate Limits:** https://huggingface.co/docs/api-inference/rate-limits

### **Deployment Platforms:**
- **Railway:** https://docs.railway.app
- **Render:** https://render.com/docs
- **Vercel:** https://vercel.com/docs
- **Netlify:** https://docs.netlify.com

### **Project Documentation:**
- `docs/CARA_CEK_QUOTA_LLM.md` - Cara cek quota
- `docs/INFORMASI_TOKEN_LLM.md` - Info token usage
- `docs/LLM_SETUP_SUMMARY.md` - Setup LLM

---

## ✅ **Kesimpulan**

### **Apakah Bisa Di-Deploy?**
**✅ YA, BISA!** Project ini siap untuk deployment karena:
1. ✅ Menggunakan HuggingFace Inference API (cloud-based)
2. ✅ Tidak perlu GPU atau server khusus
3. ✅ Backend hanya perlu koneksi internet
4. ✅ Dependencies sudah lengkap

### **Yang Perlu Diperhatikan:**
1. ⚠️ **Quota & Rate Limits** - Monitor usage secara rutin
2. ⚠️ **Environment Variables** - Pastikan semua API keys sudah diset
3. ⚠️ **Error Handling** - Handle quota exceeded dengan baik
4. ⚠️ **Security** - Jangan expose API keys di frontend

### **Rekomendasi:**
- **Development:** Gunakan free tier semua (HuggingFace + Hosting)
- **Production (Traffic Rendah):** Free tier masih bisa, monitor quota
- **Production (Traffic Tinggi):** Pertimbangkan paid tier untuk reliability

**Selamat Deploy! 🚀**

---

**Terakhir Diupdate:** 2024  
**Versi:** 1.0

