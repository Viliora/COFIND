-- =====================================================
-- VERIFIKASI INDEX SUDAH DIBUAT
-- =====================================================
-- Jalankan query ini di Supabase SQL Editor untuk cek index

-- 1. Cek semua index yang ada di table reviews
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'reviews'
ORDER BY indexname;

-- Expected output: Harus ada idx_reviews_place_created

-- 2. Test performa query dengan EXPLAIN ANALYZE
EXPLAIN ANALYZE
SELECT id, user_id, place_id, rating, text, created_at, updated_at
FROM reviews
WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U'
ORDER BY created_at DESC
LIMIT 25;

-- Expected output:
-- - Execution Time harus < 100ms (idealnya < 50ms)
-- - Harus menggunakan "Index Scan using idx_reviews_place_created"
-- - BUKAN "Seq Scan" (table scan)

-- 3. Cek RLS policy untuk reviews table
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies
WHERE tablename = 'reviews';

-- Expected: Policy untuk SELECT harus simple (USING true)

-- 4. Cek statement timeout untuk role
SELECT name, setting, unit
FROM pg_settings
WHERE name LIKE '%timeout%'
  AND name IN ('statement_timeout', 'idle_in_transaction_session_timeout');

-- Expected: statement_timeout harus >= 30000 (30 detik)

-- 5. Cek jumlah reviews per place_id
SELECT place_id, COUNT(*) as review_count
FROM reviews
WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U'
GROUP BY place_id;

-- Jika review_count banyak (> 100), query mungkin perlu pagination
