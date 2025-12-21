-- =====================================================
-- FIX RLS POLICY UNTUK PERFORMA OPTIMAL
-- =====================================================
-- Jalankan query ini HANYA JIKA verifikasi menunjukkan RLS policy yang complex

-- 1. Drop existing policies
DROP POLICY IF EXISTS "Reviews viewable by everyone" ON reviews;
DROP POLICY IF EXISTS "Public reviews are viewable by everyone" ON reviews;
DROP POLICY IF EXISTS "Enable read access for all users" ON reviews;

-- 2. Create simple SELECT policy (NO COMPLEX CHECKS)
CREATE POLICY "simple_select_reviews"
ON reviews FOR SELECT
USING (true);  -- PALING SIMPLE: semua user bisa read semua reviews

-- 3. Create policies untuk INSERT, UPDATE, DELETE
CREATE POLICY "auth_insert_reviews"
ON reviews FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "auth_update_reviews"
ON reviews FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "auth_delete_reviews"
ON reviews FOR DELETE
USING (auth.uid() = user_id);

-- 4. PENTING: Pastikan RLS enabled
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

-- 5. Fix policies untuk review_photos
DROP POLICY IF EXISTS "Photos viewable by everyone" ON review_photos;
CREATE POLICY "simple_select_photos"
ON review_photos FOR SELECT
USING (true);

CREATE POLICY "auth_insert_photos"
ON review_photos FOR INSERT
WITH CHECK (
  auth.uid() IN (
    SELECT user_id FROM reviews WHERE id = review_id
  )
);

-- 6. Fix policies untuk review_replies
DROP POLICY IF EXISTS "Replies viewable by everyone" ON review_replies;
CREATE POLICY "simple_select_replies"
ON review_replies FOR SELECT
USING (true);

CREATE POLICY "auth_insert_replies"
ON review_replies FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- 7. Increase statement timeout
ALTER ROLE authenticated SET statement_timeout = '30s';
ALTER ROLE anon SET statement_timeout = '30s';

-- 8. Reload PostgREST
NOTIFY pgrst, 'reload config';

-- 9. Verify policies
SELECT tablename, policyname, cmd, qual::text
FROM pg_policies
WHERE tablename IN ('reviews', 'review_photos', 'review_replies')
ORDER BY tablename, cmd;
