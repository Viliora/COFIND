-- ============================================
-- QUICK FIX: Enable Public Read for Reviews
-- ============================================
-- Jalankan ini di Supabase SQL Editor
-- Ini memastikan reviews bisa dibaca tanpa authentication

-- Step 1: Enable RLS (jika belum)
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_replies ENABLE ROW LEVEL SECURITY;

-- Step 2: Drop existing SELECT policies (bersihkan dulu)
DROP POLICY IF EXISTS "public_read_reviews" ON reviews;
DROP POLICY IF EXISTS "public_read_profiles" ON profiles;
DROP POLICY IF EXISTS "public_read_photos" ON review_photos;
DROP POLICY IF EXISTS "public_read_replies" ON review_replies;
DROP POLICY IF EXISTS "Reviews are viewable by everyone" ON reviews;
DROP POLICY IF EXISTS "Profiles are viewable by everyone" ON profiles;
DROP POLICY IF EXISTS "Photos are viewable by everyone" ON review_photos;
DROP POLICY IF EXISTS "Replies are viewable by everyone" ON review_replies;

-- Step 3: Create new public read policies
CREATE POLICY "public_read_reviews" ON reviews
  FOR SELECT TO public USING (true);

CREATE POLICY "public_read_profiles" ON profiles
  FOR SELECT TO public USING (true);

CREATE POLICY "public_read_photos" ON review_photos
  FOR SELECT TO public USING (true);

CREATE POLICY "public_read_replies" ON review_replies
  FOR SELECT TO public USING (true);

-- Step 4: Verify
SELECT tablename, policyname, cmd 
FROM pg_policies 
WHERE tablename IN ('reviews', 'profiles', 'review_photos', 'review_replies')
  AND cmd = 'SELECT';





