# ✨ Personalized Recommendations - Tanpa LLM

Dokumen ini menjelaskan bagaimana sistem **Personalized Recommendations** bekerja **TANPA LLM** dan **TANPA login user**.

---

## ✅ **JAWABAN: LOGIS & BISA DIBUAT!**

**Ya, personalized recommendations BISA dibuat** tanpa LLM dan tanpa login user karena:

1. ✅ **Favorit tersimpan di localStorage** - Tidak perlu login
2. ✅ **Data reviews tersedia** - Bisa dianalisis untuk ekstrak features
3. ✅ **Rule-based filtering** - Tidak perlu LLM, cukup algoritma sederhana
4. ✅ **Content-based recommendations** - Berdasarkan similarity features

---

## 🎯 **Cara Kerja**

### **1. Data Collection (Tanpa Login)**

**Favorit User:**
- Tersimpan di `localStorage` dengan key `favoriteShops`
- Format: Array of `place_id` strings
- Contoh: `["ChIJ9RWUkaZZHS4RYeuZOYAMQ-4", "ChIJDcJgropZHS4RKuh8s52jy9U"]`

**Data yang Digunakan:**
- `places.json` - Data semua coffee shops
- `reviews.json` - Reviews per coffee shop
- Favorit dari localStorage

### **2. Feature Extraction (Tanpa LLM)**

**Ekstrak Features dari Reviews Favorit:**

Sistem menganalisis reviews dari coffee shop favorit untuk menemukan **keywords/features** yang sering muncul:

```javascript
// Contoh: User favoritkan coffee shop dengan reviews:
// - "wifi kencang, cocok buat belajar"
// - "ruangan dingin, cozy, colokan banyak"

// Features yang diekstrak:
{
  wifi: true,
  belajar: true,
  dingin: true,
  cozy: true,
  colokan: true
}
```

**Features yang Dideteksi:**
- `wifi` - WiFi bagus/kencang/stabil
- `cozy` - Nyaman, hangat, tenang
- `belajar` - Cocok untuk belajar/kerja/WFC
- `colokan` - Stopkontak banyak
- `musholla` - Ada tempat sholat
- `sofa` - Kursi nyaman/sofa
- `dingin` - AC, ruangan dingin
- `aesthetic` - Estetik, kekinian
- `live_music` - Live music
- `parkir` - Parkiran luas
- `24_jam` - Buka 24 jam
- `gaming` - Cocok untuk gaming

### **3. Similarity Matching**

**Cari Coffee Shop Serupa:**

Sistem mencari coffee shop lain yang memiliki **features serupa** dengan favorit:

```javascript
// Favorit user memiliki features: {wifi: true, belajar: true, cozy: true}
// Coffee shop lain yang memiliki features serupa akan direkomendasikan
```

**Scoring System:**
- **Feature Similarity (50%)** - Seberapa mirip features-nya
- **Rating Score (30%)** - Rating tinggi lebih diprioritaskan
- **Location Score (20%)** - Coffee shop dekat dengan favorit lebih baik

### **4. Recommendations Output**

**Hasil:**
- Coffee shop dengan similarity score tertinggi
- Exclude coffee shop yang sudah di-favoritkan
- Minimal rating 4.0
- Maksimal 8-10 recommendations

---

## 📊 **Algoritma Detail**

### **Step 1: Ekstrak Features dari Favorit**

```javascript
// Ambil semua favorit
const favorites = ["place_id_1", "place_id_2"];

// Untuk setiap favorit, ambil reviews
const reviews = reviews_by_place_id[place_id_1];

// Ekstrak features dari reviews
const features = extractFeaturesFromReviews(reviews);
// Result: {wifi: true, belajar: true, cozy: true}
```

### **Step 2: Aggregate Features**

```javascript
// Jika user punya 3 favorit dengan features:
// Favorit 1: {wifi: true, cozy: true}
// Favorit 2: {wifi: true, belajar: true}
// Favorit 3: {cozy: true, dingin: true}

// Aggregate (weighted):
{
  wifi: 2,      // Muncul 2x
  cozy: 2,      // Muncul 2x
  belajar: 1,   // Muncul 1x
  dingin: 1     // Muncul 1x
}

// Normalize:
{
  wifi: 1.0,    // Paling penting
  cozy: 1.0,    // Paling penting
  belajar: 0.5,
  dingin: 0.5
}
```

### **Step 3: Score Semua Coffee Shop**

```javascript
// Untuk setiap coffee shop:
const score = 
  (featureSimilarity * 0.5) +    // 50% dari features
  (ratingScore * 0.3) +          // 30% dari rating
  (locationScore * 0.2);         // 20% dari lokasi
```

### **Step 4: Sort & Filter**

```javascript
// Sort berdasarkan score tertinggi
// Filter: exclude favorites, min rating 4.0
// Ambil top 8-10
```

---

## 🔍 **Contoh Skenario**

### **Skenario 1: User dengan 3 Favorit**

**Favorit User:**
1. Coffee Shop A - Reviews: "wifi kencang, cocok buat belajar"
2. Coffee Shop B - Reviews: "cozy, ruangan dingin, colokan banyak"
3. Coffee Shop C - Reviews: "aesthetic, instagramable, parkir luas"

**Features yang Diekstrak:**
- `wifi` (muncul 1x)
- `belajar` (muncul 1x)
- `cozy` (muncul 1x)
- `dingin` (muncul 1x)
- `colokan` (muncul 1x)
- `aesthetic` (muncul 1x)
- `parkir` (muncul 1x)

**Recommendations:**
- Coffee shop yang memiliki kombinasi features tersebut
- Prioritas: yang memiliki lebih banyak features yang sama
- Rating tinggi lebih diprioritaskan

### **Skenario 2: User dengan 1 Favorit**

**Favorit User:**
- Coffee Shop X - Reviews: "wifi bagus, cozy, cocok buat belajar"

**Features:**
- `wifi`, `cozy`, `belajar`

**Recommendations:**
- Coffee shop dengan `wifi` + `cozy` + `belajar`
- Atau minimal 2 dari 3 features
- Rating tinggi lebih diprioritaskan

---

## 💡 **Keuntungan Pendekatan Ini**

### **✅ Tanpa LLM:**
- Tidak perlu quota token
- Tidak perlu API call
- Cepat dan efisien
- Bisa dijalankan di client-side

### **✅ Tanpa Login:**
- Menggunakan localStorage
- Tidak perlu backend authentication
- Privacy-friendly (data tetap di browser)
- Tidak perlu database user

### **✅ Personalized:**
- Berdasarkan preferensi user yang sebenarnya
- Update real-time saat user tambah/hapus favorit
- Relevan dengan history user

---

## ⚙️ **Konfigurasi**

### **Options yang Bisa Disesuaikan:**

```javascript
getPersonalizedRecommendations(favoriteShops, allShops, {
  maxResults: 10,        // Maksimal 10 recommendations
  minRating: 4.0,        // Minimal rating 4.0
  excludeFavorites: true, // Exclude yang sudah di-favoritkan
  weightFeatures: 0.5,   // Weight untuk features (50%)
  weightRating: 0.3,     // Weight untuk rating (30%)
  weightLocation: 0.2,   // Weight untuk lokasi (20%)
});
```

### **Tuning Recommendations:**

**Jika ingin lebih fokus pada features:**
```javascript
weightFeatures: 0.7,
weightRating: 0.2,
weightLocation: 0.1,
```

**Jika ingin lebih fokus pada rating:**
```javascript
weightFeatures: 0.3,
weightRating: 0.5,
weightLocation: 0.2,
```

---

## 📍 **Lokasi di UI**

**Katalog "Rekomendasi untuk Anda" muncul:**
- ✅ Di atas "Baru Saja Dilihat"
- ✅ Di atas "All Coffee Shops"
- ✅ Hanya jika user punya favorit (minimal 1)
- ✅ Tidak muncul saat ada search atau filter aktif

**Urutan Katalog:**
1. **Rekomendasi untuk Anda** (Personalized) - Jika ada favorit
2. **Baru Saja Dilihat** - Jika ada recently viewed
3. **Featured Coffee Shops** - Top 5
4. **Top Rated** - Rating 4.8-5.0
5. **Hidden Gem** - Rating tinggi, review sedikit
6. **All Coffee Shops** - Semua coffee shop

---

## 🔧 **Cara Test**

### **1. Tambah Favorit:**
1. Buka detail coffee shop
2. Klik tombol favorit (❤️)
3. Kembali ke halaman utama

### **2. Lihat Recommendations:**
1. Scroll ke bawah
2. Lihat katalog "✨ Rekomendasi untuk Anda"
3. Coffee shop yang direkomendasikan akan muncul

### **3. Verifikasi:**
- Recommendations tidak termasuk coffee shop yang sudah di-favoritkan
- Recommendations memiliki features yang mirip dengan favorit
- Recommendations memiliki rating minimal 4.0

---

## 🎯 **Keterbatasan**

### **1. Minimal Data:**
- Perlu minimal **1 favorit** untuk generate recommendations
- Semakin banyak favorit, semakin akurat recommendations

### **2. Feature Detection:**
- Hanya detect features yang ada di mapping keywords
- Tidak bisa detect features baru yang tidak ada di mapping

### **3. Location-based:**
- Hanya akurat jika coffee shop memiliki data lokasi
- Tidak bisa hitung jarak jika lokasi tidak ada

### **4. No Collaborative Filtering:**
- Tidak bisa "user yang suka X juga suka Y" (perlu data user lain)
- Hanya content-based filtering

---

## 🚀 **Future Improvements (Opsional)**

### **1. Machine Learning (Tanpa LLM):**
- Train simple ML model di client-side
- Gunakan TensorFlow.js untuk recommendations
- Tidak perlu API, semua di browser

### **2. Collaborative Filtering:**
- Jika ada backend dengan data user
- "User yang suka X juga suka Y"
- Perlu login dan database

### **3. Advanced Features:**
- Time-based recommendations (pagi/sore/malam)
- Weather-based recommendations
- Price-based filtering

---

## ✅ **Kesimpulan**

### **Apakah Logis?**
**✅ YA, sangat logis!**

- Personalized recommendations **TIDAK PERLU LLM**
- Bisa dibuat dengan **rule-based algorithms**
- Menggunakan **content-based filtering**
- Data dari **localStorage** (tidak perlu login)

### **Apakah Bisa Dibuat?**
**✅ YA, sudah dibuat!**

- ✅ Utility: `frontend-cofind/src/utils/personalizedRecommendations.js`
- ✅ Integration: `frontend-cofind/src/pages/ShopList.jsx`
- ✅ Katalog: "✨ Rekomendasi untuk Anda"

### **Cara Kerja:**
1. User tambah favorit → Tersimpan di localStorage
2. Sistem analisis reviews favorit → Ekstrak features
3. Sistem cari coffee shop serupa → Scoring & ranking
4. Tampilkan recommendations → Katalog "Rekomendasi untuk Anda"

**Tidak perlu LLM, tidak perlu login, semuanya bekerja di client-side! 🎉**

---

**Terakhir Diupdate:** 2024  
**Versi:** 1.0

