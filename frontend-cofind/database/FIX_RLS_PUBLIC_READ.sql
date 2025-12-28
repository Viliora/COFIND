-- ============================================
-- FIX RLS: Enable RLS with Public Read Access
-- ============================================
-- Tujuan: Reviews bisa dibaca siapa saja (termasuk guest/anonymous)
-- tetapi hanya user yang login bisa insert/update/delete

-- ============================================
-- STEP 1: Check current RLS status
-- ============================================
SELECT 
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('reviews', 'review_photos', 'review_replies', 'profiles');

-- ============================================
-- STEP 2: Check existing policies
-- ============================================
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual
FROM pg_policies 
WHERE tablename IN ('reviews', 'review_photos', 'review_replies', 'profiles')
ORDER BY tablename, policyname;

-- ============================================
-- STEP 3: Enable RLS on all tables
-- ============================================
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_photos ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_replies ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- ============================================
-- STEP 4: Drop existing policies (clean slate)
-- ============================================
DROP POLICY IF EXISTS "Reviews are viewable by everyone" ON reviews;
DROP POLICY IF EXISTS "Users can insert their own reviews" ON reviews;
DROP POLICY IF EXISTS "Users can update their own reviews" ON reviews;
DROP POLICY IF EXISTS "Users can delete their own reviews" ON reviews;
DROP POLICY IF EXISTS "public_read_reviews" ON reviews;
DROP POLICY IF EXISTS "auth_insert_reviews" ON reviews;
DROP POLICY IF EXISTS "auth_update_reviews" ON reviews;
DROP POLICY IF EXISTS "auth_delete_reviews" ON reviews;

DROP POLICY IF EXISTS "Photos are viewable by everyone" ON review_photos;
DROP POLICY IF EXISTS "Users can insert their own photos" ON review_photos;
DROP POLICY IF EXISTS "public_read_photos" ON review_photos;
DROP POLICY IF EXISTS "auth_insert_photos" ON review_photos;

DROP POLICY IF EXISTS "Replies are viewable by everyone" ON review_replies;
DROP POLICY IF EXISTS "Users can insert their own replies" ON review_replies;
DROP POLICY IF EXISTS "Users can update their own replies" ON review_replies;
DROP POLICY IF EXISTS "Users can delete their own replies" ON review_replies;
DROP POLICY IF EXISTS "public_read_replies" ON review_replies;
DROP POLICY IF EXISTS "auth_insert_replies" ON review_replies;

DROP POLICY IF EXISTS "Profiles are viewable by everyone" ON profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON profiles;
DROP POLICY IF EXISTS "public_read_profiles" ON profiles;
DROP POLICY IF EXISTS "auth_update_profiles" ON profiles;

-- ============================================
-- STEP 5: Create new policies
-- ============================================

-- REVIEWS TABLE
-- 1. PUBLIC READ: Anyone can read reviews (including anonymous/guest)
CREATE POLICY "public_read_reviews" ON reviews
FOR SELECT
TO public  -- 'public' role includes anonymous users
USING (true);

-- 2. AUTH INSERT: Only authenticated users can create reviews
CREATE POLICY "auth_insert_reviews" ON reviews
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

-- 3. AUTH UPDATE: Only owner can update their reviews
CREATE POLICY "auth_update_reviews" ON reviews
FOR UPDATE
TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- 4. AUTH DELETE: Only owner can delete their reviews
CREATE POLICY "auth_delete_reviews" ON reviews
FOR DELETE
TO authenticated
USING (auth.uid() = user_id);

-- REVIEW_PHOTOS TABLE
-- 1. PUBLIC READ: Anyone can view photos
CREATE POLICY "public_read_photos" ON review_photos
FOR SELECT
TO public
USING (true);

-- 2. AUTH INSERT: Only authenticated users can upload photos
CREATE POLICY "auth_insert_photos" ON review_photos
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1 FROM reviews 
        WHERE reviews.id = review_photos.review_id 
        AND reviews.user_id = auth.uid()
    )
);

-- 3. AUTH DELETE: Only owner can delete photos
CREATE POLICY "auth_delete_photos" ON review_photos
FOR DELETE
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM reviews 
        WHERE reviews.id = review_photos.review_id 
        AND reviews.user_id = auth.uid()
    )
);

-- REVIEW_REPLIES TABLE
-- 1. PUBLIC READ: Anyone can view replies
CREATE POLICY "public_read_replies" ON review_replies
FOR SELECT
TO public
USING (true);

-- 2. AUTH INSERT: Only authenticated users can create replies
CREATE POLICY "auth_insert_replies" ON review_replies
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

-- 3. AUTH UPDATE: Only owner can update replies
CREATE POLICY "auth_update_replies" ON review_replies
FOR UPDATE
TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- 4. AUTH DELETE: Only owner can delete replies
CREATE POLICY "auth_delete_replies" ON review_replies
FOR DELETE
TO authenticated
USING (auth.uid() = user_id);

-- PROFILES TABLE
-- 1. PUBLIC READ: Anyone can view profiles (for displaying username)
CREATE POLICY "public_read_profiles" ON profiles
FOR SELECT
TO public
USING (true);

-- 2. AUTH UPDATE: Only owner can update their profile
CREATE POLICY "auth_update_profiles" ON profiles
FOR UPDATE
TO authenticated
USING (auth.uid() = id)
WITH CHECK (auth.uid() = id);

-- 3. AUTH INSERT: System can insert profiles (for new users)
-- This is handled by trigger, but we allow for fallback
CREATE POLICY "auth_insert_profiles" ON profiles
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = id);

-- ============================================
-- STEP 6: Verify policies created
-- ============================================
SELECT 
    tablename,
    policyname,
    cmd as operation,
    roles,
    permissive
FROM pg_policies 
WHERE tablename IN ('reviews', 'review_photos', 'review_replies', 'profiles')
ORDER BY tablename, cmd;

-- ============================================
-- STEP 7: Test public access (should work without auth)
-- ============================================
-- Run this to test if public read works:
-- SELECT * FROM reviews LIMIT 5;





