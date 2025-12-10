# 📍 Lokasi File dan Prompt LLM untuk AI Analyzer

## 🗂️ File yang Mengatur Prompt LLM

### **File Utama: `app.py`**
**Path**: `C:\Users\User\cofind\app.py`

Ini adalah file backend Flask yang mengatur semua prompt dan logika LLM untuk halaman AI Analyzer.

---

## 📋 Struktur Prompt LLM di `app.py`

### 1. **Endpoint API**: `/api/llm/analyze`
**Lokasi**: Line ~597-763

Endpoint ini menerima request dari frontend (halaman AI Analyzer) dan mengirim ke Hugging Face LLM.

```python
@app.route('/api/llm/analyze', methods=['POST'])
def llm_analyze():
    # ... kode endpoint
```

---

### 2. **System Prompt** (Instruksi Utama untuk LLM)
**Lokasi**: Line ~640-671

Ini adalah instruksi utama yang memberitahu LLM bagaimana cara bekerja dan aturan apa yang harus diikuti.

```python
system_prompt = f"""Anda adalah asisten rekomendasi coffee shop yang AKURAT dan MEMBANTU...

DATA COFFEE SHOP DI {location.upper()} DENGAN INFORMASI LENGKAP:
{places_context}

🎯 CARA KERJA REKOMENDASI:
1. Analisis kata kunci yang diminta user
2. Cari coffee shop yang SESUAI dengan kriteria
3. Jika ada review yang menyebutkan kata kunci, kutip PERSIS
4. Jika tidak ada review yang menyebutkan, tetap rekomendasikan yang SESUAI
...
"""
```

**Yang Diatur di Sini:**
- ✅ Cara LLM menganalisis kata kunci
- ✅ Aturan anti-halusinasi
- ✅ Cara mengutip review
- ✅ Logika rekomendasi

---

### 3. **User Prompt** (Request Spesifik dari User)
**Lokasi**: Line ~683-723

Ada 3 jenis task yang berbeda:

#### A. Task: `recommend` (Default untuk AI Analyzer)
**Lokasi**: Line ~683-723

```python
elif task == 'recommend':
    user_content = f"""KATA KUNCI PREFERENSI saya:
{user_text}

Tugas Anda: Berikan rekomendasi coffee shop terbaik yang SESUAI...

FORMAT WAJIB untuk setiap rekomendasi:
🏆 [Nama Coffee Shop] - Rating X/5.0
📍 Alamat: [alamat lengkap]
🗺️ Google Maps: [URL dari data]

📝 Berdasarkan Ulasan Pengunjung:
...
"""
```

**Yang Diatur di Sini:**
- ✅ Format output response
- ✅ Logika prioritas rekomendasi
- ✅ Cara bold/highlight kata kunci
- ✅ Contoh-contoh yang benar dan salah

#### B. Task: `summarize`
**Lokasi**: Line ~678-682

#### C. Task: `analyze` (default)
**Lokasi**: Line ~725-727

---

### 4. **Parameter LLM** (Mengatur Perilaku Model)
**Lokasi**: Line ~733-741

```python
response = hf_client.chat.completions.create(
    model=HF_MODEL,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ],
    max_tokens=1536,      # Panjang maksimal response
    temperature=0.4,      # Kreativitas vs Akurasi (0-1)
    top_p=0.9            # Keberagaman token
)
```

**Parameter Penting:**
- `max_tokens`: Berapa banyak kata yang bisa dihasilkan (1536 = ~1000-1200 kata)
- `temperature`: 
  - 0.0-0.3 = Sangat akurat, rigid
  - 0.4-0.6 = **Balanced** (saat ini)
  - 0.7-1.0 = Kreatif, bisa halusinasi
- `top_p`: Keberagaman pemilihan kata (0.9 = cukup fleksibel)

---

### 5. **Fungsi Fetch Data Coffee Shop**
**Lokasi**: Line ~362-479

```python
def _fetch_coffeeshops_with_reviews_context(location_str, max_shops=10):
    # Fetch coffee shops dari Google Places API
    # Ambil reviews untuk setiap coffee shop
    # Format menjadi context string untuk LLM
```

**Yang Diatur di Sini:**
- ✅ Berapa banyak coffee shop yang di-fetch (default: 10)
- ✅ Berapa banyak review per coffee shop (max: 5)
- ✅ Format data yang dikirim ke LLM

---

## 🔧 Cara Mengubah Perilaku LLM

### 1. **Mengubah Instruksi/Aturan**
Edit bagian **System Prompt** (line ~640-671)

Contoh:
```python
# Tambah aturan baru
"8. Prioritaskan coffee shop dengan rating > 4.5"
```

### 2. **Mengubah Format Output**
Edit bagian **User Prompt** untuk task `recommend` (line ~683-723)

Contoh:
```python
# Tambah field baru
"⏰ Jam Buka: [jam buka dari data]"
```

### 3. **Mengubah Kreativitas vs Akurasi**
Edit **Parameter LLM** (line ~733-741)

```python
# Lebih akurat (kurang fleksibel)
temperature=0.2

# Lebih fleksibel (bisa kurang akurat)
temperature=0.6
```

### 4. **Mengubah Jumlah Coffee Shop yang Dianalisis**
Edit fungsi `_fetch_coffeeshops_with_reviews_context` (line ~633)

```python
# Sebelum (10 coffee shops)
places_context = _fetch_coffeeshops_with_reviews_context(location, max_shops=10)

# Sesudah (20 coffee shops)
places_context = _fetch_coffeeshops_with_reviews_context(location, max_shops=20)
```

---

## 📊 Flow Lengkap: User Input → LLM Response

```
1. User ketik di AI Analyzer (frontend)
   ↓
2. Frontend kirim POST ke /api/llm/analyze
   ↓
3. Backend (app.py) terima request
   ↓
4. Fetch coffee shops + reviews dari Google Places API
   ↓
5. Build System Prompt + User Prompt
   ↓
6. Kirim ke Hugging Face LLM (Meta-Llama)
   ↓
7. LLM proses dengan parameter (temperature, max_tokens, dll)
   ↓
8. LLM generate response
   ↓
9. Backend kirim response ke frontend
   ↓
10. Frontend tampilkan dengan bold/formatting
```

---

## 🛠️ Perbaikan yang Baru Saja Dilakukan

### **Masalah Sebelumnya:**
- Prompt terlalu **RIGID** dan **KETAT**
- LLM hanya merekomendasikan jika review **PERSIS** menyebutkan kata kunci
- Input "buka malam, musholla" → Response: "Tidak ada yang sesuai" ❌

### **Solusi:**
1. **System Prompt** lebih fleksibel:
   - Jika review menyebut kata kunci → Kutip review ✅
   - Jika tidak menyebut TAPI coffee shop cocok → Tetap rekomendasikan ✅
   
2. **User Prompt** dengan logika prioritas:
   - PRIORITAS 1: Review yang menyebutkan kata kunci
   - PRIORITAS 2: Coffee shop bagus (rating tinggi) dengan review positif lain
   - PRIORITAS 3: Jujur jika tidak ada yang cocok

3. **Parameter** lebih balanced:
   - `temperature`: 0.3 → 0.4 (lebih fleksibel)
   - `top_p`: 0.85 → 0.9 (lebih beragam)

---

## 🧪 Testing Setelah Perbaikan

### Test Case 1: "wifi bagus, cozy"
**Expected**: Rekomendasikan coffee shop dengan review yang menyebut wifi/cozy

### Test Case 2: "buka malam, 24 jam, musholla"
**Expected**: 
- Jika ada review tentang itu → Kutip review
- Jika tidak ada review → Tetap rekomendasikan coffee shop terbaik dengan review positif

### Test Case 3: "kolam renang, karaoke"
**Expected**: Jujur katakan tidak ada yang sesuai (karena ini bukan fitur coffee shop)

---

## 🚀 Cara Menerapkan Perubahan

1. **Restart Backend**:
```bash
# Windows
.\restart-backend.bat

# Manual
# 1. Stop backend (Ctrl+C)
# 2. Start ulang: python app.py
```

2. **Test di Browser**:
   - Buka halaman AI Analyzer
   - Input: "buka malam, 24 jam, musholla, tempat ibadah"
   - Klik "Dapatkan Rekomendasi"
   - Verifikasi response sekarang lebih logis dan membantu

---

## 📝 Catatan Penting

- **System Prompt** = Aturan umum dan cara kerja LLM
- **User Prompt** = Request spesifik dan format output
- **Temperature** = Keseimbangan akurasi vs fleksibilitas
- **Context** = Data coffee shop dari Google Places API

Semua perubahan pada prompt akan langsung mempengaruhi cara LLM merespons!

---

**File Lokasi**: `app.py`  
**Line System Prompt**: ~640-671  
**Line User Prompt (recommend)**: ~683-723  
**Line Parameter LLM**: ~733-741  
**Terakhir Diupdate**: 27 November 2025

