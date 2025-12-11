# 📝 Penjelasan Prompt LLM di app.py

Dokumen ini menjelaskan bagian kode yang Anda tandai di `app.py` (line 782-871 dan 984-1138).

---

## 🎯 **Nama Bagian Kode**

Bagian kode yang Anda tandai disebut:

### **1. System Prompt** (Line 782-871)
- **Nama:** `system_prompt`
- **Lokasi:** Line 777-871
- **Fungsi:** Instruksi dasar untuk LLM tentang peran dan aturan umum

### **2. User Prompt / User Content** (Line 984-1138)
- **Nama:** `user_content`
- **Lokasi:** Line 979-1138 (untuk task 'recommend') dan Line 1107-1138 (untuk task 'analyze')
- **Fungsi:** Instruksi spesifik untuk setiap request user

**Istilah Teknis:** Ini adalah **Prompt Engineering** - teknik menulis instruksi untuk mengontrol output LLM.

---

## 📋 **Struktur Prompt**

### **System Prompt** (Line 777-871)
```python
system_prompt = f"""Anda adalah asisten rekomendasi coffee shop...
[Instruksi umum dan aturan]
"""
```

**Isi:**
- Peran LLM (asisten rekomendasi)
- Aturan utama (line 782-786)
- Format output (line 806-812)
- Kriteria relevansi (line 841-862)
- Dll.

### **User Prompt** (Line 979-1138)
```python
user_content = f"""KATA KUNCI PREFERENSI saya:
{user_text}
[Instruksi spesifik untuk request ini]
"""
```

**Isi:**
- Kata kunci dari user
- Aturan ketat untuk task ini
- Format output yang harus diikuti
- Contoh output yang benar/salah

---

## 🎨 **Tentang Penggunaan Emoji**

### **✅ Emoji di PROMPT (Boleh & Disarankan)**

**Emoji digunakan di PROMPT untuk:**
- ✅ **Visual organization** - Memudahkan LLM memahami struktur
- ✅ **Highlighting** - Menandai bagian penting
- ✅ **Readability** - Membuat prompt lebih mudah dibaca

**Contoh di kode Anda:**
```python
🎯 ATURAN UTAMA:        # Section header
🚨 WAJIB - REVIEW:      # Warning/Penting
⚠️ ATURAN ANTI-HALUSINASI:  # Warning
🚫 FORMAT OUTPUT - DILARANG:  # Larangan
✅ FORMAT OUTPUT - WAJIB:     # Format yang benar
📋 CARA MENGUTIP REVIEW:      # Panduan
🔍 KRITERIA RELEVANSI:        # Kriteria
```

**Kenapa pakai emoji di prompt?**
- LLM lebih mudah memahami struktur dengan visual markers
- Emoji membantu LLM fokus pada bagian penting
- Meningkatkan akurasi pemahaman instruksi

### **❌ Emoji di OUTPUT (Dilarang)**

**Di aturan output, Anda MELARANG LLM menggunakan emoji:**

```803:803:app.py
- JANGAN gunakan emoji apapun (🏆📍📝🗺️🎯☕💡 dll)
```

```1020:1020:app.py
- JANGAN gunakan emoji apapun (🏆📍📝🗺️🎯☕💡 dll)
```

**Kenapa dilarang?**
- Output harus **clean** dan **professional**
- Emoji bisa mengganggu parsing response
- Format output harus konsisten untuk frontend

---

## 📊 **Perbandingan**

| Aspek | Prompt (Code) | Output (LLM Response) |
|-------|---------------|----------------------|
| **Emoji** | ✅ Boleh (untuk organization) | ❌ Dilarang |
| **Format** | Structured dengan emoji | Plain text, structured |
| **Tujuan** | Instruksi untuk LLM | Response untuk user |

---

## 💡 **Best Practices**

### **1. Emoji di Prompt**

**✅ Gunakan untuk:**
- Section headers (🎯, 🚨, ⚠️, ✅, 🚫)
- Highlighting penting
- Visual organization

**❌ Jangan gunakan untuk:**
- Contoh output yang benar (karena output tidak boleh pakai emoji)
- Format yang harus diikuti LLM

### **2. Struktur Prompt**

**Format yang baik:**
```
🎯 SECTION 1: [Judul]
- Point 1
- Point 2

🚨 SECTION 2: [Peringatan]
- Aturan penting
```

**Format yang buruk:**
```
Semua aturan dicampur tanpa struktur
Tidak ada visual markers
Sulit dibaca
```

### **3. Konsistensi**

**✅ Konsisten:**
- Gunakan emoji yang sama untuk section yang sama
- Format yang konsisten di semua prompt

**❌ Tidak konsisten:**
- Kadang pakai emoji, kadang tidak
- Format berbeda-beda

---

## 🔍 **Contoh di Kode Anda**

### **System Prompt (Line 782-871):**
```python
🎯 ATURAN UTAMA:              # Visual marker untuk section
🚨 WAJIB - REVIEW:            # Warning marker
⚠️ ATURAN ANTI-HALUSINASI:    # Warning marker
🚫 FORMAT OUTPUT - DILARANG:  # Prohibition marker
✅ FORMAT OUTPUT - WAJIB:     # Success marker
📋 CARA MENGUTIP REVIEW:      # Guide marker
🔍 KRITERIA RELEVANSI:        # Search/criteria marker
```

### **User Prompt (Line 984-1138):**
```python
⚠️ ATURAN KETAT:             # Warning
🚨 WAJIB - SETIAP REKOMENDASI: # Critical requirement
🔗 PENTING - SINONIM:        # Link/connection marker
🚫 DILARANG KERAS:           # Strong prohibition
✅ FORMAT OUTPUT WAJIB:      # Required format
🚨 PERINGATAN PENTING:       # Important warning
```

### **Output yang Dilarang (Line 803, 1020):**
```
❌ JANGAN gunakan emoji apapun (🏆📍📝🗺️🎯☕💡 dll)
```

**Contoh Output yang SALAH:**
```
❌ 🏆 Toko Kami - Rating 4.8/5.0
❌ 📍 Alamat: Jl. Ahmad Yani
❌ 📝 Review: ...
```

**Contoh Output yang BENAR:**
```
✅ 1. **Toko Kami**
Rating: 4.8
Alamat: Jl. Ahmad Yani
Berdasarkan Ulasan Pengunjung: ...
```

---

## ✅ **Kesimpulan**

### **1. Nama Bagian Kode:**
- **System Prompt** (line 782-871) - Instruksi umum
- **User Prompt / User Content** (line 984-1138) - Instruksi spesifik

### **2. Tentang Emoji:**

**Di PROMPT (Code):**
- ✅ **BOLEH & DISARANKAN** - Untuk visual organization
- ✅ Membantu LLM memahami struktur
- ✅ Meningkatkan readability

**Di OUTPUT (LLM Response):**
- ❌ **DILARANG** - Output harus clean text
- ❌ Dilarang di aturan (line 803, 1020)
- ❌ Untuk konsistensi dan parsing

### **3. Best Practice:**
- ✅ Gunakan emoji di prompt untuk organization
- ✅ Jangan gunakan emoji di contoh output
- ✅ Konsisten dengan format yang sama

---

**Terakhir Diupdate:** 2024  
**Versi:** 1.0

