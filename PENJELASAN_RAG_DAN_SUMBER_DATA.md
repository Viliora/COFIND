# 📚 Penjelasan RAG dan Sumber Data Proyek CoFind

## ❓ Pertanyaan User

1. **Apakah bisa membuat link verifikasi review ke Google Maps?**
   - ✅ **SUDAH DITAMBAHKAN** - Setiap review sekarang memiliki link `[Verifikasi: URL]` yang mengarah ke profil reviewer di Google Maps

2. **Kenapa response LLM ada coffee shop yang tidak ada di 60 coffee shop dari API?**
   - ❌ **TIDAK ADA RAG** - Proyek ini TIDAK menggunakan RAG
   - ✅ **Penjelasan lengkap di bawah**

---

## 🔍 Apakah Proyek Ini Menggunakan RAG?

### **JAWABAN: TIDAK ❌**

Proyek ini **TIDAK menggunakan RAG (Retrieval-Augmented Generation)** dalam arti teknis yang sebenarnya.

### **Apa yang Sebenarnya Terjadi:**

Proyek ini menggunakan **"In-Context Learning"** atau **"Prompt-Based Context Injection"**, bukan RAG.

---

## 📊 Perbedaan RAG vs In-Context Learning

| Aspek | RAG (Retrieval-Augmented Generation) | In-Context Learning (Proyek Ini) |
|-------|--------------------------------------|----------------------------------|
| **Vector Database** | ✅ Ada (Pinecone, Weaviate, FAISS) | ❌ Tidak ada |
| **Embedding** | ✅ Ada (text → vector) | ❌ Tidak ada |
| **Semantic Search** | ✅ Ada (similarity search) | ❌ Tidak ada |
| **External Knowledge** | ✅ Disimpan di vector DB | ✅ Fetch real-time dari API |
| **Context Injection** | ✅ Hasil retrieval → prompt | ✅ Data API → prompt |
| **Persistence** | ✅ Data tersimpan | ❌ Fetch setiap request |

---

## 🏗️ Arsitektur Sistem Proyek CoFind

### **Flow Data:**

```
1. User Input (Frontend)
   ↓
2. POST /api/llm/analyze (Backend)
   ↓
3. Fetch Coffee Shops dari Google Places API
   - Text Search: "coffee shop Pontianak"
   - Ambil 10 coffee shops pertama (max_shops=10)
   ↓
4. Untuk setiap coffee shop:
   - Fetch Place Details (get_place_details)
   - Ambil 5 reviews per coffee shop
   ↓
5. Format data menjadi string context
   ↓
6. Inject context ke LLM prompt
   ↓
7. LLM (Llama) generate response
   ↓
8. Response dikirim ke Frontend
```

---

## 📍 Sumber Data Eksternal

### **1. Google Places API** (Satu-satunya sumber data)

**Endpoint yang Digunakan:**

#### A. **Text Search API**
- **URL**: `https://maps.googleapis.com/maps/api/place/textsearch/json`
- **Fungsi**: Mencari coffee shop di lokasi tertentu
- **Parameter**:
  ```python
  {
      'query': 'coffee shop Pontianak',
      'language': 'id',
      'key': GOOGLE_PLACES_API_KEY
  }
  ```
- **Hasil**: List coffee shops (max 20 dari Google)
- **Yang Diambil**: **10 pertama** (`max_shops=10`)

**Lokasi Kode**: `app.py` Line ~377-392

```python
def _fetch_coffeeshops_with_reviews_context(location_str, max_shops=10):
    base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        'query': f'coffee shop {location_str}',
        'language': 'id',
        'key': GOOGLE_PLACES_API_KEY
    }
    response = requests.get(base_url, params=params)
    data = response.json()
    all_shops = data.get('results', [])[:max_shops]  # Ambil 10 pertama
```

#### B. **Place Details API**
- **URL**: `https://maps.googleapis.com/maps/api/place/details/json`
- **Fungsi**: Mendapatkan detail lengkap coffee shop + reviews
- **Parameter**:
  ```python
  {
      'place_id': place_id,
      'fields': 'name,formatted_address,rating,reviews,geometry,...',
      'language': 'id',
      'key': GOOGLE_PLACES_API_KEY
  }
  ```
- **Hasil**: Detail coffee shop + **5 reviews terbaru**

**Lokasi Kode**: `app.py` Line ~200-280

```python
def get_place_details(place_id):
    base_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        'place_id': place_id,
        'fields': 'name,formatted_address,rating,user_ratings_total,reviews,...',
        'language': 'id',
        'key': GOOGLE_PLACES_API_KEY
    }
    # ...
    reviews = result.get('reviews', [])  # Max 5 reviews dari Google
```

---

## 🔢 Kenapa LLM Bisa Merekomendasikan Coffee Shop yang Tidak Ada di 60 Coffee Shop?

### **JAWABAN: TIDAK MUNGKIN ❌**

LLM **TIDAK BISA** merekomendasikan coffee shop yang tidak ada di data yang diberikan, karena:

1. **LLM hanya menerima 10 coffee shops** (bukan 60)
   - `max_shops=10` di `app.py` line 633
   
2. **LLM tidak punya akses internet**
   - LLM hanya melihat data yang ada di prompt
   
3. **Context injection ketat**
   - Semua data coffee shop diformat sebagai string dan dimasukkan ke prompt

### **Kemungkinan Penyebab:**

#### **Skenario 1: User Melihat 60 Coffee Shop di Halaman Beranda**
- Halaman beranda (`ShopList.jsx`) fetch **semua** coffee shops dari API
- Halaman AI Analyzer hanya menggunakan **10 coffee shops pertama**
- **Solusi**: Ini memang by design untuk efisiensi

#### **Skenario 2: LLM Halusinasi (Mengarang Nama)**
- Jika prompt tidak strict, LLM bisa mengarang nama coffee shop
- **Solusi**: Sudah diperbaiki dengan prompt strict di update terakhir

#### **Skenario 3: Google Places API Memberikan Hasil Berbeda**
- API Text Search bisa memberikan hasil berbeda tiap request
- Bergantung pada lokasi, waktu, dan popularitas
- **Solusi**: Ini normal behavior dari Google Places API

---

## 🔧 Cara Mengubah Jumlah Coffee Shop untuk LLM

### **Saat Ini: 10 Coffee Shops**

**Lokasi**: `app.py` Line 633

```python
places_context = _fetch_coffeeshops_with_reviews_context(location, max_shops=10)
```

### **Untuk Mengubah Menjadi 20 Coffee Shops:**

```python
places_context = _fetch_coffeeshops_with_reviews_context(location, max_shops=20)
```

### **⚠️ Trade-offs:**

| Jumlah | Pros | Cons |
|--------|------|------|
| 10 | ✅ Cepat, efisien | ❌ Pilihan terbatas |
| 20 | ✅ Lebih banyak pilihan | ❌ Lebih lambat, context lebih besar |
| 30+ | ✅ Pilihan maksimal | ❌ Sangat lambat, bisa exceed token limit |

**Rekomendasi**: Tetap di **10-15 coffee shops** untuk performa optimal.

---

## 📝 Apakah Ini RAG?

### **Definisi RAG yang Benar:**

RAG (Retrieval-Augmented Generation) memiliki komponen:

1. ✅ **Document Store** - Database untuk menyimpan dokumen
2. ✅ **Embedding Model** - Convert text → vector
3. ✅ **Vector Database** - Pinecone, Weaviate, FAISS, Chroma
4. ✅ **Retriever** - Semantic search berdasarkan similarity
5. ✅ **Generator** - LLM yang generate response

### **Proyek CoFind:**

1. ❌ **Document Store** - Tidak ada, fetch real-time dari API
2. ❌ **Embedding Model** - Tidak ada
3. ❌ **Vector Database** - Tidak ada
4. ❌ **Retriever** - Tidak ada semantic search
5. ✅ **Generator** - Ada (Llama via Hugging Face)

### **Kesimpulan:**

Proyek ini menggunakan **"API-Augmented Generation"** atau **"In-Context Learning"**, bukan RAG.

---

## 🎯 Implementasi RAG yang Sebenarnya (Jika Ingin)

Jika ingin implementasi RAG yang sebenarnya:

### **Arsitektur RAG:**

```
1. Indexing Phase (One-time):
   - Fetch semua coffee shops dari Google Places
   - Extract reviews dan informasi
   - Convert ke embeddings (text → vector)
   - Simpan di vector database (Pinecone/FAISS)

2. Query Phase (Runtime):
   - User input: "wifi bagus, cozy"
   - Convert query ke embedding
   - Semantic search di vector DB
   - Retrieve top-k relevant coffee shops
   - Inject ke LLM prompt
   - Generate response
```

### **Tools yang Dibutuhkan:**

1. **Embedding Model**: 
   - OpenAI Embeddings
   - Sentence-Transformers (open-source)
   
2. **Vector Database**:
   - Pinecone (cloud)
   - FAISS (local)
   - Weaviate (open-source)
   - Chroma (lightweight)

3. **RAG Framework**:
   - LangChain
   - LlamaIndex

### **Keuntungan RAG:**

- ✅ Semantic search (cari berdasarkan makna, bukan keyword)
- ✅ Lebih scalable (bisa handle ribuan coffee shops)
- ✅ Lebih cepat (tidak perlu fetch API setiap request)
- ✅ Offline capability

### **Kekurangan RAG:**

- ❌ Lebih kompleks untuk setup
- ❌ Butuh vector database (cost tambahan)
- ❌ Data bisa outdated (perlu re-indexing berkala)

---

## ✅ Update Terbaru: Link Verifikasi Review

### **Fitur Baru:**

Setiap review sekarang memiliki link `[Verifikasi: URL]` yang mengarah ke profil reviewer di Google Maps.

**Contoh Output:**

```
📝 Berdasarkan Ulasan Pengunjung:
• "**Wifinya kencang** banget, cocok buat kerja" - Ahmad (5⭐) [Verifikasi: https://www.google.com/maps/contrib/...]
```

**Cara Kerja:**

1. Backend mengambil `author_url` dari Google Places API
2. Format: `[Verifikasi: URL]`
3. Frontend render sebagai button hijau dengan icon ✓
4. Klik button → buka profil reviewer di Google Maps (tab baru)

**Lokasi Kode:**

- Backend: `app.py` Line ~430-450
- Frontend: `frontend-cofind/src/components/LLMAnalyzer.jsx` Line ~13-60

---

## 📊 Ringkasan

| Pertanyaan | Jawaban |
|------------|---------|
| Apakah menggunakan RAG? | ❌ Tidak, menggunakan In-Context Learning |
| Dari mana data diambil? | ✅ Google Places API (Text Search + Place Details) |
| Berapa coffee shop yang dianalisis LLM? | ✅ 10 coffee shops (bisa diubah) |
| Kenapa LLM rekomendasikan yang tidak ada? | ❌ Tidak mungkin, kecuali halusinasi (sudah diperbaiki) |
| Apakah review bisa diverifikasi? | ✅ Ya, sekarang ada link [Verifikasi: URL] |

---

**Dibuat**: 27 November 2025  
**Tujuan**: Menjelaskan arsitektur sistem dan menjawab pertanyaan tentang RAG  
**Status**: ✅ Lengkap dengan link verifikasi review

