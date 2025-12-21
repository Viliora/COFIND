# 🔴 TROUBLESHOOTING: Timeout Error Setelah Index Dibuat

## Situasi
✅ Index sudah dibuat di Supabase  
❌ Masih tetap timeout setelah refresh (F5)  
❌ Error: "Supabase request timeout after 20 seconds"

## Penyebab Kemungkinan

### 1. Index Belum Aktif / Tidak Terpakai
**Verifikasi:**
```sql
-- Jalankan di Supabase SQL Editor
SELECT indexname FROM pg_indexes WHERE tablename = 'reviews';
```

**Expected Output:**
```
idx_reviews_place_created
idx_reviews_place_id
idx_reviews_created_at
```

Jika TIDAK ADA, index belum dibuat. Jalankan lagi:
```sql
CREATE INDEX IF NOT EXISTS idx_reviews_place_created 
ON reviews (place_id, created_at DESC);
```

### 2. Query Tidak Menggunakan Index (Seq Scan)
**Verifikasi:**
```sql
EXPLAIN ANALYZE
SELECT id, user_id, place_id, rating, text, created_at, updated_at
FROM reviews
WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U'
ORDER BY created_at DESC
LIMIT 25;
```

**Good Output (FAST):**
```
-> Index Scan using idx_reviews_place_created on reviews
   Execution Time: 23.456 ms  ✅ < 100ms
```

**Bad Output (SLOW):**
```
-> Seq Scan on reviews  ❌ TABLE SCAN!
   Execution Time: 15243.123 ms  ❌ > 1000ms
```

**Fix jika Seq Scan:**
```sql
-- Force PostgreSQL to update statistics
ANALYZE reviews;

-- Rebuild index
DROP INDEX IF EXISTS idx_reviews_place_created;
CREATE INDEX idx_reviews_place_created ON reviews (place_id, created_at DESC);
ANALYZE reviews;
```

### 3. RLS Policy Terlalu Complex
**Verifikasi:**
```sql
SELECT tablename, policyname, cmd, qual::text
FROM pg_policies
WHERE tablename = 'reviews';
```

**Good Policy (FAST):**
```sql
policyname: simple_select_reviews
cmd: SELECT
qual: true  ✅ SIMPLE!
```

**Bad Policy (SLOW):**
```sql
qual: auth.uid() IN (SELECT user_id FROM something WHERE ...)  ❌ COMPLEX SUBQUERY!
```

**Fix jika Complex:**
Jalankan file `FIX_RLS_POLICY.sql`:
```sql
DROP POLICY IF EXISTS "Reviews viewable by everyone" ON reviews;

CREATE POLICY "simple_select_reviews"
ON reviews FOR SELECT
USING (true);  -- Paling simple: semua orang bisa read

NOTIFY pgrst, 'reload config';
```

### 4. Too Many Rows (> 1000 reviews)
**Verifikasi:**
```sql
SELECT place_id, COUNT(*) as review_count
FROM reviews
GROUP BY place_id
ORDER BY review_count DESC
LIMIT 10;
```

Jika > 1000 reviews per place, query bisa lambat meski pakai index.

**Fix:** Sudah ada LIMIT 25 di query, seharusnya OK.

### 5. Network / Connection Issue
**Cek:**
- Buka Supabase Dashboard → Database → Performance
- Lihat CPU usage (jika > 80%, restart project)
- Cek koneksi internet (gunakan 4G/WiFi stabil)
- Test ping ke Supabase: `ping cpnzglvpqyugtacodwtr.supabase.co`

### 6. Statement Timeout Belum Dinaikkan
**Verifikasi:**
```sql
SHOW statement_timeout;
```

Expected: `30s` atau lebih

**Fix:**
```sql
ALTER ROLE authenticated SET statement_timeout = '30s';
ALTER ROLE anon SET statement_timeout = '30s';
NOTIFY pgrst, 'reload config';
```

## Checklist Lengkap

Jalankan semua query ini secara berurutan:

```sql
-- 1. Verifikasi index ada
SELECT indexname FROM pg_indexes WHERE tablename = 'reviews';

-- 2. Test performa query
EXPLAIN ANALYZE
SELECT * FROM reviews 
WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U' 
ORDER BY created_at DESC LIMIT 25;

-- 3. Cek RLS policy
SELECT policyname, cmd, qual::text 
FROM pg_policies 
WHERE tablename = 'reviews';

-- 4. Cek timeout setting
SHOW statement_timeout;

-- 5. Cek jumlah rows
SELECT COUNT(*) FROM reviews;

-- 6. Update statistics
ANALYZE reviews;

-- 7. Jika masih lambat, recreate index
DROP INDEX IF EXISTS idx_reviews_place_created;
CREATE INDEX idx_reviews_place_created ON reviews (place_id, created_at DESC);
ANALYZE reviews;

-- 8. Verify index digunakan
EXPLAIN ANALYZE
SELECT * FROM reviews 
WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U' 
ORDER BY created_at DESC LIMIT 25;
```

## Hasil yang Diharapkan

Setelah fix:
- ✅ Query selesai dalam < 100ms (bukan 20+ detik)
- ✅ EXPLAIN ANALYZE menunjukkan "Index Scan" (bukan "Seq Scan")
- ✅ Tidak ada timeout error di console
- ✅ Reviews langsung muncul setelah refresh (F5)

## Jika Masih Timeout Setelah Semua Langkah

### Option A: Increase Frontend Timeout
Edit `frontend-cofind/src/components/ReviewList.jsx`:
```javascript
const baseTimeout = 20000; // Ubah jadi 30000 atau 45000
```

### Option B: Restart Supabase Project
1. Buka Supabase Dashboard
2. Settings → General
3. Klik "Pause project"
4. Tunggu 1 menit
5. Klik "Restore project"

### Option C: Upgrade Supabase Plan
Jika free tier:
- CPU usage bisa terbatas
- Consider upgrade ke Pro plan untuk performa lebih baik

## Quick Fix Commands

**Copy-paste ini ke Supabase SQL Editor:**

```sql
-- ALL-IN-ONE FIX SCRIPT
BEGIN;

-- Drop old policies
DROP POLICY IF EXISTS "Reviews viewable by everyone" ON reviews;
DROP POLICY IF EXISTS "Public reviews are viewable by everyone" ON reviews;

-- Create simple policy
CREATE POLICY "simple_select_reviews" ON reviews FOR SELECT USING (true);

-- Recreate index
DROP INDEX IF EXISTS idx_reviews_place_created;
CREATE INDEX idx_reviews_place_created ON reviews (place_id, created_at DESC);

-- Update timeout
ALTER ROLE authenticated SET statement_timeout = '30s';
ALTER ROLE anon SET statement_timeout = '30s';

-- Update statistics
ANALYZE reviews;

-- Reload config
NOTIFY pgrst, 'reload config';

COMMIT;

-- Verify
SELECT 'Index created:' as status, indexname FROM pg_indexes WHERE tablename = 'reviews' AND indexname LIKE 'idx_reviews%';
SELECT 'Policy created:' as status, policyname FROM pg_policies WHERE tablename = 'reviews';
SELECT 'Timeout setting:' as status, setting FROM pg_settings WHERE name = 'statement_timeout';
```

## Support

Jika masih ada masalah setelah semua langkah di atas:
1. Screenshot hasil `EXPLAIN ANALYZE`
2. Screenshot hasil `pg_policies`
3. Screenshot console error
4. Beri tahu detail yang di-screenshot

## Summary

**90% kasus timeout disebabkan oleh:**
1. Index tidak terpakai (Seq Scan instead of Index Scan) → Fix: `ANALYZE reviews`
2. RLS policy terlalu complex → Fix: `USING (true)` untuk SELECT
3. Statement timeout terlalu pendek → Fix: `ALTER ROLE ... SET statement_timeout = '30s'`

**Solusi paling efektif:**
Jalankan "ALL-IN-ONE FIX SCRIPT" di atas, tunggu 30 detik, lalu refresh browser.
