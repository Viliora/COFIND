# Optimasi Query Supabase untuk Mencegah Timeout

## 🔧 Masalah yang Diperbaiki

### **Masalah:**
Request ke Supabase timeout setelah 15 detik saat fetch reviews, menyebabkan error:
```
[ReviewList] Error fetching from Supabase: Error: Supabase request timeout after 15 seconds
```

### **Penyebab:**
1. **Query tidak optimal** - Fetch semua data tanpa limit
2. **Join dengan banyak tabel** - Join dengan `profiles`, `review_photos`, dan `review_replies` bisa lambat
3. **Tidak ada index** - Database mungkin tidak punya index pada `place_id` dan `created_at`
4. **Fetch terlalu banyak data** - Tidak ada limit, bisa fetch ratusan review sekaligus

---

## 🔄 Perbaikan yang Dibuat

### 1. **Optimasi Query - Tambahkan Limit**

**Sebelum:**
```javascript
const fetchPromise = supabase
  .from('reviews')
  .select(`...`)
  .eq('place_id', placeId)
  .order('created_at', { ascending: false });
  // ❌ Tidak ada limit - bisa fetch ratusan review
```

**Sesudah:**
```javascript
const fetchPromise = supabase
  .from('reviews')
  .select(`...`)
  .eq('place_id', placeId)
  .order('created_at', { ascending: false })
  .limit(100); // ✅ Limit to 100 reviews to prevent timeout
```

**Manfaat:**
- Mengurangi jumlah data yang di-fetch
- Mencegah timeout pada coffee shop dengan banyak review
- 100 review sudah cukup untuk UI display (bisa ditambah pagination nanti)

### 2. **Database Indexes - Pastikan Index Ada**

**File Baru:** `frontend-cofind/supabase-indexes.sql`

**Indexes yang Dibuat:**
```sql
-- CRITICAL: Index untuk query berdasarkan place_id
CREATE INDEX IF NOT EXISTS idx_reviews_place_id ON reviews(place_id);
CREATE INDEX IF NOT EXISTS idx_reviews_place_id_created_at ON reviews(place_id, created_at DESC);

-- Index untuk join dengan tabel lain
CREATE INDEX IF NOT EXISTS idx_review_photos_review_id ON review_photos(review_id);
CREATE INDEX IF NOT EXISTS idx_review_replies_review_id ON review_replies(review_id);
```

**Manfaat:**
- Query berdasarkan `place_id` menjadi **sangat cepat** (dari full table scan → index lookup)
- Join dengan `review_photos` dan `review_replies` lebih cepat
- Sorting berdasarkan `created_at` lebih efisien

---

## 📋 Langkah Implementasi

### **Langkah 1: Jalankan SQL Script untuk Indexes**

1. Buka **Supabase Dashboard** → **SQL Editor**
2. Copy-paste isi file `supabase-indexes.sql`
3. Klik **Run** untuk membuat indexes
4. Verifikasi dengan query:
   ```sql
   SELECT 
     tablename,
     indexname,
     indexdef
   FROM pg_indexes
   WHERE schemaname = 'public'
     AND tablename = 'reviews'
   ORDER BY indexname;
   ```

### **Langkah 2: Verifikasi Query Sudah Dioptimalkan**

1. Buka file `frontend-cofind/src/components/ReviewList.jsx`
2. Pastikan query sudah menggunakan `.limit(100)`
3. Test dengan membuka detail coffee shop
4. Cek Network tab - request seharusnya lebih cepat

### **Langkah 3: Monitor Performance**

1. Buka **Supabase Dashboard** → **Database** → **Query Performance**
2. Cek query yang lambat
3. Pastikan query menggunakan index (lihat "Index Scan" bukan "Seq Scan")

---

## ✅ Hasil Setelah Optimasi

### Sebelum:
- ❌ Query timeout setelah 15 detik
- ❌ Fetch semua review tanpa limit
- ❌ Tidak ada index → full table scan
- ❌ Join dengan banyak tabel lambat

### Sesudah:
- ✅ Query lebih cepat (dengan index)
- ✅ Limit 100 review (mencegah fetch terlalu banyak)
- ✅ Index pada `place_id` dan `created_at` → query cepat
- ✅ Join lebih efisien dengan index pada foreign keys

---

## 🧪 Testing

### Test Case 1: Query dengan Index
1. Jalankan SQL script untuk membuat indexes
2. Buka detail coffee shop dengan banyak review (>50)
3. **Expected**: 
   - Request selesai dalam < 5 detik
   - Tidak ada timeout
   - Reviews muncul dengan cepat

### Test Case 2: Query Performance
1. Buka Supabase Dashboard → Query Performance
2. Jalankan query manual:
   ```sql
   SELECT * FROM reviews 
   WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U' 
   ORDER BY created_at DESC 
   LIMIT 100;
   ```
3. **Expected**:
   - Query menggunakan index (`Index Scan`)
   - Execution time < 100ms

### Test Case 3: Limit Effectiveness
1. Buka detail coffee shop dengan >100 review
2. **Expected**:
   - Hanya fetch 100 review terbaru
   - Request cepat (tidak timeout)
   - UI tetap responsif

---

## 📊 Monitoring

### Console Logs untuk Debugging:
- `[ReviewList] Fetching reviews from Supabase ...` - Request dimulai
- `[ReviewList] Supabase fetch result: {dataCount: X}` - Jumlah review yang di-fetch
- **TIDAK ada** timeout error ✅

### Network Tab:
- Request ke Supabase selesai dalam < 5 detik ✅
- Response size reasonable (tidak terlalu besar) ✅
- Status 200 (bukan timeout) ✅

### Supabase Dashboard:
- Query menggunakan index (`Index Scan`) ✅
- Execution time < 100ms ✅
- Tidak ada slow query warning ✅

---

## 🔧 Troubleshooting

### Masalah: Masih Timeout Setelah Optimasi

**Solusi:**
1. **Cek Index**: Pastikan index sudah dibuat (jalankan `supabase-indexes.sql`)
2. **Cek Query**: Pastikan query menggunakan `.limit(100)`
3. **Cek Network**: Throttle network di DevTools untuk test
4. **Cek Supabase Status**: Pastikan Supabase tidak sedang maintenance

### Masalah: Query Masih Lambat

**Solusi:**
1. **Cek Query Performance**: Buka Supabase Dashboard → Query Performance
2. **Cek Index Usage**: Pastikan query menggunakan index (bukan full table scan)
3. **Reduce Limit**: Coba kurangi limit dari 100 ke 50
4. **Optimize Select**: Hanya select field yang diperlukan (bukan `*`)

### Masalah: Index Tidak Dibuat

**Solusi:**
1. **Cek SQL Script**: Pastikan script `supabase-indexes.sql` benar
2. **Cek Permissions**: Pastikan user punya permission untuk create index
3. **Cek Supabase Plan**: Free tier mungkin punya limit untuk index

---

## 📝 Catatan Penting

1. **Limit Value**:
   - **100 reviews** adalah sweet spot (cukup untuk UI, tidak terlalu banyak)
   - Bisa ditambah ke 200 jika diperlukan
   - Bisa dikurangi ke 50 jika masih timeout

2. **Index Strategy**:
   - **Composite Index** (`place_id, created_at DESC`) lebih efisien untuk query dengan ORDER BY
   - **Single Index** (`place_id`) cukup untuk filter saja
   - Index akan otomatis digunakan oleh PostgreSQL query planner

3. **Future Optimization**:
   - **Pagination**: Implement pagination untuk load lebih banyak review
   - **Lazy Loading**: Load photos dan replies on-demand (bukan di query utama)
   - **Caching**: Cache reviews di client untuk reduce API calls

---

## 🔗 Related Files

- `frontend-cofind/src/components/ReviewList.jsx` - Query optimization (added `.limit(100)`)
- `frontend-cofind/supabase-indexes.sql` - Database indexes (NEW FILE)
- `frontend-cofind/supabase-schema-safe.sql` - Schema dengan indexes dasar

---

## 📚 Referensi

- [Supabase Query Optimization](https://supabase.com/docs/guides/database/query-optimization)
- [PostgreSQL Indexes](https://www.postgresql.org/docs/current/indexes.html)
- [PostgREST Query Performance](https://postgrest.org/en/stable/api.html#performance)
