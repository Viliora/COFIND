-- ============================================
-- FIX RLS POLICY UNTUK GUEST ACCESS
-- Jalankan script ini di Supabase SQL Editor
-- ============================================

-- Pastikan RLS enabled
ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

-- Drop policy lama jika ada (untuk re-create)
DROP POLICY IF EXISTS "Reviews viewable by everyone" ON reviews;

-- Re-create policy dengan eksplisit untuk guest (unauthenticated) dan authenticated users
-- Policy ini memastikan SEMUA user (termasuk guest) bisa membaca reviews
CREATE POLICY "Reviews viewable by everyone" 
ON reviews 
FOR SELECT 
USING (true);  -- true = semua user (guest dan authenticated) bisa read

-- Verifikasi policy sudah dibuat
-- Jalankan query ini untuk verify:
-- SELECT * FROM pg_policies WHERE tablename = 'reviews' AND policyname = 'Reviews viewable by everyone';

-- Test query sebagai guest (unauthenticated)
-- Query ini seharusnya return data meskipun tidak login:
-- SELECT * FROM reviews WHERE place_id = 'ChIJDcJgropZHS4RKuh8s52jy9U' LIMIT 10;
