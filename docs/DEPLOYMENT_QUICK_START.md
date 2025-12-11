# ⚡ Deployment Quick Start

Panduan cepat untuk deploy project COFIND dengan HuggingFace LLM.

---

## 🎯 **TL;DR - Bisa Deploy!**

✅ **YA, project ini BISA di-deploy** karena menggunakan HuggingFace Inference API (cloud-based, tidak perlu GPU).

---

## 📋 **Checklist Cepat**

### **1. Environment Variables (WAJIB)**

**Backend:**
```env
GOOGLE_PLACES_API_KEY=AIzaSy...
HF_API_TOKEN=hf_...
HF_MODEL=meta-llama/Llama-3.1-8B-Instruct  # opsional
```

**Frontend:**
```env
VITE_API_BASE=https://your-backend-url.com
```

### **2. Dependencies**

**Backend:** `requirements.txt` sudah include `huggingface-hub` ✅

**Frontend:** `npm install` di folder `frontend-cofind`

---

## 🚀 **Deployment Options**

### **Option 1: Railway (Backend) + Vercel (Frontend)** ⭐ Recommended

#### **Backend di Railway:**
1. Sign up: https://railway.app
2. New Project → Deploy from GitHub
3. Select repo
4. Add environment variables:
   - `GOOGLE_PLACES_API_KEY`
   - `HF_API_TOKEN`
   - `HF_MODEL` (opsional)
5. Deploy! (auto-deploy dari Git push)

#### **Frontend di Vercel:**
1. Sign up: https://vercel.com
2. Import GitHub repo
3. Root directory: `frontend-cofind`
4. Build command: `npm run build`
5. Output directory: `dist`
6. Environment variable: `VITE_API_BASE` = Railway backend URL
7. Deploy!

**Total Cost:** **$0** (free tier) atau **~$5-10/bulan** (paid)

---

### **Option 2: Render (Backend) + Netlify (Frontend)**

#### **Backend di Render:**
1. Sign up: https://render.com
2. New Web Service
3. Connect GitHub repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. Add environment variables
7. Deploy!

#### **Frontend di Netlify:**
1. Sign up: https://netlify.com
2. Import GitHub repo
3. Base directory: `frontend-cofind`
4. Build command: `npm run build`
5. Publish directory: `dist`
6. Environment variable: `VITE_API_BASE`
7. Deploy!

**Total Cost:** **$0** (free tier dengan limit)

---

### **Option 3: Heroku (Full Stack)**

#### **Backend:**
```bash
heroku create cofind-backend
heroku config:set GOOGLE_PLACES_API_KEY=...
heroku config:set HF_API_TOKEN=...
git push heroku main
```

#### **Frontend:**
- Deploy ke Vercel/Netlify (lebih mudah untuk frontend)

**Total Cost:** **~$7-15/bulan** (Heroku tidak ada free tier lagi)

---

## ⚠️ **Peringatan Penting**

### **1. HuggingFace Quota**
- **Free tier:** 30 req/min, ~1,000 req/day
- **Monitor:** https://huggingface.co/settings/billing
- **Upgrade:** Jika traffic tinggi, pertimbangkan paid tier ($9+/bulan)

### **2. Google Places API**
- **Free credit:** $200 (lalu pay-as-you-go)
- **Monitor:** Google Cloud Console
- **Cost:** ~$0.017 per request

### **3. Security**
- ✅ Jangan commit `.env` ke Git
- ✅ Set environment variables di platform
- ✅ Gunakan HTTPS di production
- ✅ Set CORS dengan domain spesifik

---

## 🔧 **Troubleshooting**

### **Error: "HF_API_TOKEN tidak dikonfigurasi"**
→ Set `HF_API_TOKEN` di environment variables platform

### **Error: 402 Payment Required**
→ Quota HuggingFace habis, cek di dashboard atau upgrade

### **Error: CORS**
→ Update CORS di `app.py` dengan frontend domain production

### **Error: Timeout**
→ Increase timeout di platform atau optimize context size

---

## 📚 **Dokumentasi Lengkap**

Lihat `docs/DEPLOYMENT_GUIDE_LLM.md` untuk:
- Detail lengkap setiap platform
- Best practices
- Error handling
- Monitoring
- Cost estimation

---

## ✅ **Quick Commands**

```bash
# Test local sebelum deploy
python app.py

# Build frontend
cd frontend-cofind
npm run build

# Check requirements
pip install -r requirements.txt

# Test LLM endpoint
curl -X POST http://localhost:5000/api/llm/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "wifi bagus"}'
```

---

**Selamat Deploy! 🚀**

