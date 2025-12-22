-- =====================================================
-- VERIFIKASI LENGKAP SETELAH FIX
-- =====================================================

-- 1. ✅ Cek Index Ada dan Aktif
SELECT 
    'Index Check' as step,
    indexname, 
    indexdef
FROM pg_indexes 
WHERE tablename = 'reviews' 
  AND indexname = 'idx_reviews_place_created';

-- Expected: 1 row dengan indexname = idx_reviews_place_created

-- 2. ✅ Cek RLS Policy Simple
SELECT 
    'Policy Check' as step,
    policyname, 
    cmd,
    qual::text as policy_rule
FROM pg_policies 
WHERE tablename = 'reviews' 
  AND cmd = 'SELECT';

-- Expected: simple_select_reviews dengan qual = true

-- 3. ✅ Test Performa Query (PENTING!)
EXPLAIN ANALYZE
SELECT id, user_id, place_id, rating, text, created_at, updated_at
FROM reviews
WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U'
ORDER BY created_at DESC
LIMIT 25;

-- Expected Output:
-- -> Index Scan using idx_reviews_place_created on reviews
-- Execution Time: < 100ms (idealnya < 50ms)
-- 
-- ❌ BAD Output (jika ini yang muncul):
-- -> Seq Scan on reviews
-- Execution Time: > 1000ms

-- 4. ✅ Cek Statement Timeout
SHOW statement_timeout;

-- Expected: 30s atau 30000

-- 5. ✅ Cek Jumlah Reviews
SELECT 
    'Review Count' as step,
    COUNT(*) as total_reviews
FROM reviews;

-- 6. ✅ Cek Reviews per Place
SELECT 
    'Reviews per Place' as step,
    place_id, 
    COUNT(*) as review_count
FROM reviews
GROUP BY place_id
ORDER BY review_count DESC
LIMIT 5;
