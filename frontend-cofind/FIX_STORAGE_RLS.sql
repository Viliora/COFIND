-- ============================================
-- FIX STORAGE RLS POLICY FOR AVATAR UPLOAD
-- ============================================
-- Fixes: "new row violates row-level security policy" error
-- when uploading avatar photos

-- ============================================
-- STEP 1: Enable RLS on storage.objects (if not already enabled)
-- ============================================
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- ============================================
-- STEP 2: Drop existing policies (if any) to avoid conflicts
-- ============================================
DROP POLICY IF EXISTS "Allow authenticated users to upload avatars" ON storage.objects;
DROP POLICY IF EXISTS "Allow public to view avatars" ON storage.objects;
DROP POLICY IF EXISTS "Allow users to update own avatars" ON storage.objects;
DROP POLICY IF EXISTS "Allow users to delete own avatars" ON storage.objects;

-- Also drop old review-photos policies if they exist
DROP POLICY IF EXISTS "Allow authenticated users to upload review photos" ON storage.objects;
DROP POLICY IF EXISTS "Allow public to view review photos" ON storage.objects;
DROP POLICY IF EXISTS "Allow users to update own review photos" ON storage.objects;
DROP POLICY IF EXISTS "Allow users to delete own review photos" ON storage.objects;

-- ============================================
-- STEP 3: Create RLS policies for AVATAR uploads
-- ============================================

-- Policy 1: Allow authenticated users to UPLOAD avatars
-- Users can upload to avatars/ folder in review-photos bucket
CREATE POLICY "Allow authenticated users to upload avatars"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'review-photos' 
  AND (storage.foldername(name))[1] = 'avatars'
  AND auth.uid()::text = (storage.foldername(name))[2] -- User can only upload to their own folder
);

-- Policy 2: Allow PUBLIC to VIEW avatars (no auth required)
-- Anyone can view/download avatar images
CREATE POLICY "Allow public to view avatars"
ON storage.objects
FOR SELECT
TO public
USING (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'avatars'
);

-- Policy 3: Allow users to UPDATE their own avatars
-- Users can update metadata of their own avatar files
CREATE POLICY "Allow users to update own avatars"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'avatars'
  AND auth.uid()::text = (storage.foldername(name))[2]
)
WITH CHECK (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'avatars'
  AND auth.uid()::text = (storage.foldername(name))[2]
);

-- Policy 4: Allow users to DELETE their own avatars
-- Users can delete their own avatar files
CREATE POLICY "Allow users to delete own avatars"
ON storage.objects
FOR DELETE
TO authenticated
USING (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'avatars'
  AND auth.uid()::text = (storage.foldername(name))[2]
);

-- ============================================
-- STEP 4: Create RLS policies for REVIEW PHOTOS uploads
-- ============================================

-- Policy 5: Allow authenticated users to UPLOAD review photos
CREATE POLICY "Allow authenticated users to upload review photos"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'reviews'
);

-- Policy 6: Allow PUBLIC to VIEW review photos
CREATE POLICY "Allow public to view review photos"
ON storage.objects
FOR SELECT
TO public
USING (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'reviews'
);

-- Policy 7: Allow users to UPDATE their own review photos
CREATE POLICY "Allow users to update own review photos"
ON storage.objects
FOR UPDATE
TO authenticated
USING (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'reviews'
  AND auth.uid()::text = (storage.foldername(name))[2]
)
WITH CHECK (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'reviews'
  AND auth.uid()::text = (storage.foldername(name))[2]
);

-- Policy 8: Allow users to DELETE their own review photos
CREATE POLICY "Allow users to delete own review photos"
ON storage.objects
FOR DELETE
TO authenticated
USING (
  bucket_id = 'review-photos'
  AND (storage.foldername(name))[1] = 'reviews'
  AND auth.uid()::text = (storage.foldername(name))[2]
);

-- ============================================
-- STEP 5: Verify policies were created
-- ============================================
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
WHERE tablename = 'objects'
ORDER BY policyname;

-- ============================================
-- SUCCESS MESSAGE
-- ============================================
DO $$
BEGIN
  RAISE NOTICE '✅ Storage RLS policies created successfully!';
  RAISE NOTICE '✅ Users can now upload avatars and review photos';
  RAISE NOTICE '✅ Avatar uploads: /avatars/{userId}/{filename}';
  RAISE NOTICE '✅ Review photo uploads: /reviews/{userId}/{filename}';
END $$;

