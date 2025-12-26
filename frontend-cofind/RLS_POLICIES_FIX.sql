-- =====================================================
-- RLS POLICIES FIX UNTUK COFIND PROJECT
-- =====================================================
-- Jalankan SQL ini di Supabase SQL Editor
-- =====================================================

-- =====================================================
-- 1. REVIEWS TABLE - Cleanup & Setup
-- =====================================================

-- Hapus semua policies lama yang duplicate/conflict
DROP POLICY IF EXISTS "allow_read_all" ON reviews;
DROP POLICY IF EXISTS "auth_delete_reviews" ON reviews;
DROP POLICY IF EXISTS "auth_insert_reviews" ON reviews;
DROP POLICY IF EXISTS "auth_update_reviews" ON reviews;
DROP POLICY IF EXISTS "public_read_reviews" ON reviews;
DROP POLICY IF EXISTS "Reviews viewable by everyone" ON reviews;
DROP POLICY IF EXISTS "Users can delete own reviews" ON reviews;
DROP POLICY IF EXISTS "Users can insert own reviews" ON reviews;
DROP POLICY IF EXISTS "Users can update own reviews" ON reviews;

-- Enable RLS
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

-- Policy 1: Semua orang bisa melihat reviews (SELECT)
CREATE POLICY "reviews_select_public" ON reviews
  FOR SELECT
  TO public
  USING (true);

-- Policy 2: Authenticated users bisa insert review sendiri
CREATE POLICY "reviews_insert_own" ON reviews
  FOR INSERT
  TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);

-- Policy 3: Authenticated users bisa update review sendiri
CREATE POLICY "reviews_update_own" ON reviews
  FOR UPDATE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);

-- Policy 4: Authenticated users bisa delete review sendiri
CREATE POLICY "reviews_delete_own" ON reviews
  FOR DELETE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

-- =====================================================
-- 2. PROFILES TABLE - Cleanup & Setup
-- =====================================================

-- Hapus policies lama jika ada
DROP POLICY IF EXISTS "Profiles viewable by everyone" ON profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
DROP POLICY IF EXISTS "Users can insert own profile" ON profiles;

-- Enable RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- Policy 1: Semua orang bisa melihat profiles
CREATE POLICY "profiles_select_public" ON profiles
  FOR SELECT
  TO public
  USING (true);

-- Policy 2: Authenticated users bisa insert profile sendiri
CREATE POLICY "profiles_insert_own" ON profiles
  FOR INSERT
  TO authenticated
  WITH CHECK ((SELECT auth.uid()) = id);

-- Policy 3: Authenticated users bisa update profile sendiri
CREATE POLICY "profiles_update_own" ON profiles
  FOR UPDATE
  TO authenticated
  USING ((SELECT auth.uid()) = id)
  WITH CHECK ((SELECT auth.uid()) = id);

-- =====================================================
-- 3. FAVORITES TABLE - Cleanup & Setup
-- =====================================================

-- Hapus policies lama jika ada
DROP POLICY IF EXISTS "Users can view own favorites" ON favorites;
DROP POLICY IF EXISTS "Users can insert own favorites" ON favorites;
DROP POLICY IF EXISTS "Users can delete own favorites" ON favorites;

-- Enable RLS
ALTER TABLE favorites ENABLE ROW LEVEL SECURITY;

-- Policy 1: Authenticated users hanya bisa lihat favorites sendiri
CREATE POLICY "favorites_select_own" ON favorites
  FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

-- Policy 2: Authenticated users bisa insert favorites sendiri
CREATE POLICY "favorites_insert_own" ON favorites
  FOR INSERT
  TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);

-- Policy 3: Authenticated users bisa delete favorites sendiri
CREATE POLICY "favorites_delete_own" ON favorites
  FOR DELETE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

-- =====================================================
-- 4. WANT_TO_VISIT TABLE - Cleanup & Setup
-- =====================================================

-- Hapus policies lama jika ada
DROP POLICY IF EXISTS "Users can view own want_to_visit" ON want_to_visit;
DROP POLICY IF EXISTS "Users can insert own want_to_visit" ON want_to_visit;
DROP POLICY IF EXISTS "Users can delete own want_to_visit" ON want_to_visit;

-- Enable RLS
ALTER TABLE want_to_visit ENABLE ROW LEVEL SECURITY;

-- Policy 1: Authenticated users hanya bisa lihat want_to_visit sendiri
CREATE POLICY "want_to_visit_select_own" ON want_to_visit
  FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

-- Policy 2: Authenticated users bisa insert want_to_visit sendiri
CREATE POLICY "want_to_visit_insert_own" ON want_to_visit
  FOR INSERT
  TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);

-- Policy 3: Authenticated users bisa delete want_to_visit sendiri
CREATE POLICY "want_to_visit_delete_own" ON want_to_visit
  FOR DELETE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

-- =====================================================
-- 5. CREATE INDEXES UNTUK PERFORMANCE
-- =====================================================

-- Index untuk reviews
CREATE INDEX IF NOT EXISTS idx_reviews_user_id ON reviews(user_id);
CREATE INDEX IF NOT EXISTS idx_reviews_place_id ON reviews(place_id);
CREATE INDEX IF NOT EXISTS idx_reviews_user_place ON reviews(user_id, place_id);

-- Index untuk favorites
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_place_id ON favorites(place_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user_place ON favorites(user_id, place_id);

-- Index untuk want_to_visit
CREATE INDEX IF NOT EXISTS idx_want_to_visit_user_id ON want_to_visit(user_id);
CREATE INDEX IF NOT EXISTS idx_want_to_visit_place_id ON want_to_visit(place_id);
CREATE INDEX IF NOT EXISTS idx_want_to_visit_user_place ON want_to_visit(user_id, place_id);

-- =====================================================
-- VERIFIKASI
-- =====================================================

-- Cek policies yang sudah dibuat
SELECT 
  schemaname,
  tablename,
  policyname,
  permissive,
  roles,
  cmd,
  qual,
  with_check
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('reviews', 'profiles', 'favorites', 'want_to_visit')
ORDER BY tablename, policyname;

