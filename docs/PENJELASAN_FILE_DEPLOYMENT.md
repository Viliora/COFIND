# 📋 Penjelasan File Konfigurasi Deployment

Dokumen ini menjelaskan fungsi dan penggunaan **Procfile**, **railway.json**, dan **render.yaml** untuk deployment aplikasi.

---

## 1️⃣ **Procfile**

### **Apa Itu Procfile?**

**Procfile** adalah file konfigurasi yang digunakan oleh platform **Heroku** untuk menentukan **perintah apa yang harus dijalankan** saat aplikasi di-deploy.

### **Format:**
```
<process type>: <command>
```

### **File di Project:**
```1:1:Procfile
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120
```

### **Penjelasan Baris:**

| Bagian | Penjelasan |
|--------|------------|
| `web:` | **Process type** - Menandakan ini adalah web server (HTTP) |
| `gunicorn` | **WSGI HTTP Server** - Server untuk menjalankan aplikasi Flask/Python |
| `app:app` | **Module:Application** - `app.py` adalah file, `app` adalah Flask instance |
| `--bind 0.0.0.0:$PORT` | **Binding** - Listen di semua interface, port dari environment variable `$PORT` |
| `--workers 4` | **Workers** - Jumlah worker process (4 worker = bisa handle 4 request bersamaan) |
| `--timeout 120` | **Timeout** - Request timeout 120 detik (penting untuk LLM yang butuh waktu lama) |

### **Kapan Digunakan?**
- ✅ **Heroku** - Wajib untuk Heroku deployment
- ✅ **Platform lain** - Beberapa platform juga support Procfile (Railway, Render)

### **Contoh Lain:**
```procfile
# Web server
web: gunicorn app:app --bind 0.0.0.0:$PORT

# Background worker (jika ada)
worker: python worker.py

# Scheduled task
scheduler: python scheduler.py
```

### **Catatan Penting:**
- File harus bernama **`Procfile`** (tanpa ekstensi, huruf P besar)
- Harus di **root directory** project
- Heroku otomatis membaca file ini saat deploy

---

## 2️⃣ **railway.json**

### **Apa Itu railway.json?**

**railway.json** adalah file konfigurasi khusus untuk platform **Railway** yang menentukan bagaimana aplikasi di-build dan di-deploy.

### **File di Project:**
```1:12:railway.json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### **Penjelasan Setiap Bagian:**

#### **`$schema`**
- **Fungsi:** Validasi JSON schema (untuk autocomplete di editor)
- **Value:** URL schema dari Railway

#### **`build` Section:**
```json
"build": {
  "builder": "NIXPACKS",
  "buildCommand": "pip install -r requirements.txt"
}
```

| Field | Penjelasan |
|-------|------------|
| `builder` | **NIXPACKS** - Build system otomatis yang detect Python project |
| `buildCommand` | **Command untuk build** - Install dependencies dari requirements.txt |

**Alternatif Builder:**
- `NIXPACKS` - Auto-detect (Python, Node.js, dll)
- `DOCKERFILE` - Gunakan Dockerfile custom
- `HEROKUISH` - Compatible dengan Heroku buildpacks

#### **`deploy` Section:**
```json
"deploy": {
  "startCommand": "gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120",
  "restartPolicyType": "ON_FAILURE",
  "restartPolicyMaxRetries": 10
}
```

| Field | Penjelasan |
|-------|------------|
| `startCommand` | **Command untuk start aplikasi** - Sama seperti Procfile |
| `restartPolicyType` | **Kapan restart** - `ON_FAILURE` = restart jika crash |
| `restartPolicyMaxRetries` | **Max retry** - Restart maksimal 10 kali jika gagal |

**Restart Policy Options:**
- `ON_FAILURE` - Restart jika aplikasi crash
- `NEVER` - Tidak restart otomatis
- `ON_DEPLOY` - Restart setiap deploy

### **Kapan Digunakan?**
- ✅ **Railway** - File konfigurasi khusus untuk Railway
- ✅ **Opsional** - Railway bisa auto-detect tanpa file ini, tapi lebih baik ada

### **Keuntungan:**
- ✅ **Explicit configuration** - Jelas apa yang dijalankan
- ✅ **Version control** - Konfigurasi di Git, bukan di dashboard
- ✅ **Team collaboration** - Semua developer tahu konfigurasi

---

## 3️⃣ **render.yaml**

### **Apa Itu render.yaml?**

**render.yaml** adalah file konfigurasi untuk platform **Render** yang mendefinisikan **services** (web, worker, dll) dan konfigurasinya.

### **File di Project:**
```1:15:render.yaml
services:
  - type: web
    name: cofind-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120
    envVars:
      - key: GOOGLE_PLACES_API_KEY
        sync: false
      - key: HF_API_TOKEN
        sync: false
      - key: HF_MODEL
        value: meta-llama/Llama-3.1-8B-Instruct
        sync: false
```

### **Penjelasan Setiap Bagian:**

#### **`services` Array:**
Array yang berisi semua service yang akan di-deploy.

#### **Service Configuration:**
```yaml
- type: web              # Tipe service (web, worker, cron, dll)
  name: cofind-backend   # Nama service di dashboard Render
  env: python            # Environment (python, node, docker, dll)
```

| Field | Penjelasan |
|-------|------------|
| `type` | **Service type** - `web` = HTTP server, `worker` = background job, `cron` = scheduled task |
| `name` | **Service name** - Nama yang muncul di Render dashboard |
| `env` | **Environment** - `python`, `node`, `docker`, `static`, dll |

#### **Build & Start Commands:**
```yaml
buildCommand: pip install -r requirements.txt
startCommand: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120
```

| Field | Penjelasan |
|-------|------------|
| `buildCommand` | **Command untuk build** - Install dependencies |
| `startCommand` | **Command untuk start** - Jalankan aplikasi |

#### **Environment Variables:**
```yaml
envVars:
  - key: GOOGLE_PLACES_API_KEY
    sync: false
  - key: HF_API_TOKEN
    sync: false
  - key: HF_MODEL
    value: meta-llama/Llama-3.1-8B-Instruct
    sync: false
```

| Field | Penjelasan |
|-------|------------|
| `key` | **Nama variable** - Nama environment variable |
| `value` | **Nilai default** (opsional) - Value jika tidak diset di dashboard |
| `sync: false` | **Tidak sync** - Value tidak di-overwrite dari dashboard (lebih aman) |

**Catatan:** `sync: false` berarti value di dashboard akan digunakan, bukan value di file.

### **Kapan Digunakan?**
- ✅ **Render** - File konfigurasi untuk Render platform
- ✅ **Infrastructure as Code** - Semua konfigurasi di file, bukan manual di dashboard

### **Contoh Multiple Services:**
```yaml
services:
  # Web server
  - type: web
    name: cofind-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT

  # Background worker (jika ada)
  - type: worker
    name: cofind-worker
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python worker.py

  # Scheduled task
  - type: cron
    name: daily-cleanup
    schedule: "0 2 * * *"  # Setiap hari jam 2 pagi
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python cleanup.py
```

---

## 📊 **Perbandingan Ketiga File**

| Aspek | Procfile | railway.json | render.yaml |
|-------|----------|--------------|-------------|
| **Platform** | Heroku (utama) | Railway | Render |
| **Format** | Plain text | JSON | YAML |
| **Fungsi** | Start command saja | Build + Deploy | Full service config |
| **Environment Variables** | ❌ Tidak support | ❌ Tidak support | ✅ Support |
| **Multiple Services** | ✅ Support | ❌ Single service | ✅ Support |
| **Complexity** | ⭐ Simple | ⭐⭐ Medium | ⭐⭐⭐ Advanced |

---

## 🎯 **Kapan Menggunakan Masing-Masing?**

### **Gunakan Procfile jika:**
- ✅ Deploy ke **Heroku**
- ✅ Konfigurasi sederhana (hanya start command)
- ✅ Tidak perlu konfigurasi build yang kompleks

### **Gunakan railway.json jika:**
- ✅ Deploy ke **Railway**
- ✅ Ingin konfigurasi eksplisit untuk build & deploy
- ✅ Ingin version control untuk konfigurasi Railway

### **Gunakan render.yaml jika:**
- ✅ Deploy ke **Render**
- ✅ Perlu multiple services (web + worker + cron)
- ✅ Ingin define environment variables di file
- ✅ Ingin **Infrastructure as Code** approach

---

## 💡 **Best Practices**

### **1. Version Control**
✅ **Commit semua file** ke Git
- Semua developer tahu konfigurasi
- Mudah rollback jika ada masalah
- Dokumentasi otomatis

### **2. Environment Variables**
⚠️ **Jangan hardcode secrets** di file
- Gunakan environment variables di platform dashboard
- File hanya untuk reference/default values

### **3. Consistency**
✅ **Gunakan command yang sama** di semua file
```bash
# Semua file menggunakan command yang sama
gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120
```

### **4. Testing**
✅ **Test di local** sebelum deploy
```bash
# Test gunicorn command di local
gunicorn app:app --bind 0.0.0.0:5000 --workers 4 --timeout 120
```

---

## 🔧 **Troubleshooting**

### **Problem 1: Procfile tidak terbaca**
**Solusi:**
- Pastikan nama file **`Procfile`** (huruf P besar, tanpa ekstensi)
- Pastikan file di **root directory**
- Check format: `web: command`

### **Problem 2: railway.json tidak digunakan**
**Solusi:**
- Pastikan file di **root directory**
- Check JSON syntax valid
- Railway akan auto-detect, tapi bisa juga set manual di dashboard

### **Problem 3: render.yaml error**
**Solusi:**
- Check YAML syntax (indentation penting!)
- Pastikan `type`, `name`, `env` sudah benar
- Validate di: https://www.yamllint.com/

---

## 📚 **Referensi**

- **Procfile:** https://devcenter.heroku.com/articles/procfile
- **Railway Config:** https://docs.railway.app/reference/railway-json
- **Render Blueprint:** https://render.com/docs/blueprint-spec

---

## ✅ **Kesimpulan**

Ketiga file ini adalah **konfigurasi deployment** untuk platform berbeda:

1. **Procfile** - Heroku (simple, start command)
2. **railway.json** - Railway (build + deploy config)
3. **render.yaml** - Render (full service config dengan env vars)

**Rekomendasi:**
- ✅ **Simpan semua file** di project (untuk fleksibilitas)
- ✅ **Gunakan sesuai platform** yang dipilih
- ✅ **Jangan hardcode secrets** - gunakan environment variables

---

**Terakhir Diupdate:** 2024  
**Versi:** 1.0

