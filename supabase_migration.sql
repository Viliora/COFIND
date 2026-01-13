-- Create places table in Supabase
CREATE TABLE IF NOT EXISTS places (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  place_id TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  address TEXT,
  business_status TEXT DEFAULT 'OPERATIONAL',
  location JSONB, -- Store lat/lng as JSON
  rating DECIMAL(3,1),
  user_ratings_total INTEGER DEFAULT 0,
  price_level INTEGER,
  map_embed_url TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_places_place_id ON places(place_id);
CREATE INDEX IF NOT EXISTS idx_places_name ON places(name);
CREATE INDEX IF NOT EXISTS idx_places_location ON places USING GIN(location);

-- Enable RLS (Row Level Security)
ALTER TABLE places ENABLE ROW LEVEL SECURITY;

-- Create policy to allow read access for all users
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polname = 'Allow read access for all users'
      AND polrelid = 'public.places'::regclass
  ) THEN
    CREATE POLICY "Allow read access for all users"
      ON public.places
      FOR SELECT
      TO public
      USING (true);
  END IF;
END
$$;

-- Create policy to allow admin users to modify
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polname = 'Allow admin users to modify places'
      AND polrelid = 'public.places'::regclass
  ) THEN
    CREATE POLICY "Allow admin users to modify places"
      ON public.places
      FOR ALL
      TO authenticated
      USING (
        EXISTS (
          SELECT 1 FROM profiles
          WHERE profiles.id = auth.uid()
          AND profiles.role = 'admin'
        )
      );
  END IF;
END
$$;