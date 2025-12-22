-- ============================================
-- FAVORITES & WANT TO VISIT SCHEMA
-- Jalankan script ini di Supabase SQL Editor
-- Memastikan tabel dan RLS policy sudah benar
-- ============================================

-- Table: favorites (migrate dari localStorage)
CREATE TABLE IF NOT EXISTS favorites (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  place_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, place_id)
);

-- Table: want_to_visit (migrate dari localStorage)
CREATE TABLE IF NOT EXISTS want_to_visit (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  place_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, place_id)
);

-- Enable RLS on tables
ALTER TABLE favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE want_to_visit ENABLE ROW LEVEL SECURITY;

-- Drop existing policies before creating (to avoid conflicts)
DROP POLICY IF EXISTS "Users can view own favorites" ON favorites;
DROP POLICY IF EXISTS "Users can add favorites" ON favorites;
DROP POLICY IF EXISTS "Users can remove favorites" ON favorites;

DROP POLICY IF EXISTS "Users can view own want_to_visit" ON want_to_visit;
DROP POLICY IF EXISTS "Users can add want_to_visit" ON want_to_visit;
DROP POLICY IF EXISTS "Users can remove want_to_visit" ON want_to_visit;

-- Favorites policies
CREATE POLICY "Users can view own favorites" 
ON favorites 
FOR SELECT 
USING (auth.uid() = user_id);

CREATE POLICY "Users can add favorites" 
ON favorites 
FOR INSERT 
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can remove favorites" 
ON favorites 
FOR DELETE 
USING (auth.uid() = user_id);

-- Want to visit policies
CREATE POLICY "Users can view own want_to_visit" 
ON want_to_visit 
FOR SELECT 
USING (auth.uid() = user_id);

CREATE POLICY "Users can add want_to_visit" 
ON want_to_visit 
FOR INSERT 
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can remove want_to_visit" 
ON want_to_visit 
FOR DELETE 
USING (auth.uid() = user_id);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_favorites_place_id ON favorites(place_id);
CREATE INDEX IF NOT EXISTS idx_favorites_user_place ON favorites(user_id, place_id);

CREATE INDEX IF NOT EXISTS idx_want_to_visit_user_id ON want_to_visit(user_id);
CREATE INDEX IF NOT EXISTS idx_want_to_visit_place_id ON want_to_visit(place_id);
CREATE INDEX IF NOT EXISTS idx_want_to_visit_user_place ON want_to_visit(user_id, place_id);

-- Verify tables and policies
-- Jalankan query ini untuk verify:
-- SELECT * FROM pg_policies WHERE tablename IN ('favorites', 'want_to_visit');
-- SELECT * FROM favorites WHERE user_id = auth.uid();
-- SELECT * FROM want_to_visit WHERE user_id = auth.uid();
