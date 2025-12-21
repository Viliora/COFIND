# Perbaikan Performance & Timeout Supabase

## Masalah
Query timeout setelah 10 detik saat fetch reviews dari Supabase, terutama setelah refresh page.

## Penyebab Utama
1. **RLS Policy Lambat**: Row Level Security (RLS) policy di Supabase tidak ter-optimasi
2. **Tidak Ada Index**: Kolom `place_id` dan `created_at` tidak memiliki index
3. **Timeout Terlalu Pendek**: 10 detik mungkin tidak cukup untuk query pertama kali

## Solusi Database (WAJIB)

### 1. Tambahkan Index untuk Performa
Jalankan SQL berikut di **Supabase SQL Editor**:

```sql
-- Index untuk place_id (CRITICAL untuk performa query reviews by place)
CREATE INDEX IF NOT EXISTS idx_reviews_place_id ON reviews (place_id);

-- Index untuk created_at (untuk ORDER BY)
CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews (created_at DESC);

-- Composite index untuk place_id + created_at (OPTIMAL untuk query kita)
CREATE INDEX IF NOT EXISTS idx_reviews_place_created ON reviews (place_id, created_at DESC);

-- Index untuk review_photos
CREATE INDEX IF NOT EXISTS idx_review_photos_review_id ON review_photos (review_id);

-- Index untuk review_replies
CREATE INDEX IF NOT EXISTS idx_review_replies_review_id ON review_replies (review_id);
CREATE INDEX IF NOT EXISTS idx_review_replies_created_at ON review_replies (created_at ASC);

-- Index untuk profiles
CREATE INDEX IF NOT EXISTS idx_profiles_id ON profiles (id);
```

### 2. Optimasi RLS Policy untuk Reviews
Pastikan RLS policy menggunakan fungsi yang efisien:

```sql
-- Policy untuk READ (SELECT) - MUST BE FAST
DROP POLICY IF EXISTS "Reviews viewable by everyone" ON reviews;

CREATE POLICY "Reviews viewable by everyone"
ON reviews FOR SELECT
USING (true);  -- Simple policy, no complex checks

-- Policy untuk INSERT - hanya authenticated users
DROP POLICY IF EXISTS "Users can create reviews" ON reviews;

CREATE POLICY "Users can create reviews"
ON reviews FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Policy untuk UPDATE - hanya owner
DROP POLICY IF EXISTS "Users can update own reviews" ON reviews;

CREATE POLICY "Users can update own reviews"
ON reviews FOR UPDATE
USING (auth.uid() = user_id);

-- Policy untuk DELETE - hanya owner
DROP POLICY IF EXISTS "Users can delete own reviews" ON reviews;

CREATE POLICY "Users can delete own reviews"
ON reviews FOR DELETE
USING (auth.uid() = user_id);
```

### 3. Cek Statement Timeout untuk Role
Pastikan timeout cukup panjang:

```sql
-- Increase timeout untuk authenticated users
ALTER ROLE authenticated SET statement_timeout = '30s';

-- Increase timeout untuk anon users
ALTER ROLE anon SET statement_timeout = '30s';

-- Reload PostgREST config
NOTIFY pgrst, 'reload config';
```

### 4. Analyze & Vacuum Tables
Optimasi tabel untuk performa:

```sql
-- Analyze tables untuk update statistics
ANALYZE reviews;
ANALYZE review_photos;
ANALYZE review_replies;
ANALYZE profiles;

-- Vacuum untuk cleanup
VACUUM ANALYZE reviews;
VACUUM ANALYZE review_photos;
VACUUM ANALYZE review_replies;
VACUUM ANALYZE profiles;
```

## Solusi Frontend (Sudah diimplementasikan di code berikutnya)

### 1. Increase Timeout
- Client-level: 20s → 30s
- Query-level: 10s → 15s

### 2. Fallback ke Empty State
- Jika timeout, tampilkan empty state yang user-friendly
- Tidak show error yang menakutkan

### 3. Smart Retry
- Retry dengan backoff yang lebih smart
- Skip retry jika data sudah ada

### 4. Cache Strategy
- Cache reviews di memory untuk instant load
- Real-time update tetap jalan

## Testing

### 1. Test Index Performance
```sql
-- Test query tanpa index (BEFORE)
EXPLAIN ANALYZE
SELECT id, user_id, place_id, rating, text, created_at, updated_at
FROM reviews
WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U'
ORDER BY created_at DESC
LIMIT 25;

-- Hasil yang baik: Execution Time < 50ms
-- Hasil yang buruk: Execution Time > 1000ms
```

### 2. Test dari Browser
1. Clear site data (DevTools → Application → Clear storage)
2. Refresh page
3. Check console:
   - `[ReviewList] ⚡ Query executed in XXXms` harus < 1000ms
   - Tidak ada timeout error

### 3. Monitor Supabase Dashboard
- Database → Performance
- Cek CPU dan memory usage
- Cek slow query logs

## Expected Results

### Before (Current State)
- ❌ Query timeout setelah 10-20 detik
- ❌ Reviews tidak tampil setelah refresh
- ❌ User frustrated

### After (With Fixes)
- ✅ Query selesai dalam < 1 detik
- ✅ Reviews langsung tampil
- ✅ No more timeout errors
- ✅ Smooth UX

## Priority

1. **HIGH PRIORITY** (DO THIS FIRST):
   - Tambahkan index untuk `reviews(place_id, created_at)`
   - Simplify RLS policy untuk SELECT
   
2. **MEDIUM PRIORITY**:
   - Increase statement_timeout
   - ANALYZE tables
   
3. **LOW PRIORITY**:
   - VACUUM tables
   - Monitor dashboard

## Notes

- Index akan membuat INSERT/UPDATE sedikit lebih lambat (trade-off yang worth it)
- RLS policy yang simple (USING true) untuk SELECT adalah OK karena reviews memang public
- Statement timeout 30s adalah safe value untuk production
- Jangan lupa reload PostgREST config setelah ALTER ROLE

## Support

Jika masih timeout setelah index:
1. Cek Supabase Dashboard → Database → Logs untuk detail error
2. Run EXPLAIN ANALYZE untuk lihat query plan
3. Consider upgrade Supabase plan jika perlu compute power lebih
