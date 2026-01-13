-- Add photo_url column to places table
-- This stores Supabase Storage URL for each coffee shop photo

ALTER TABLE places
ADD COLUMN IF NOT EXISTS photo_url TEXT;

-- Update comments
COMMENT ON COLUMN places.photo_url IS 'Supabase Storage URL to coffee shop photo (https://cpnzglvpqyugtacodwtr.supabase.co/...)';

-- Example update (replace with actual URLs after uploading to Supabase Storage):
-- UPDATE places SET photo_url = 'https://cpnzglvpqyugtacodwtr.supabase.co/storage/v1/object/public/coffee_shops/ChIJ9RWUkaZZHS4RYeuZOYAMQ-4.webp' WHERE place_id = 'ChIJ9RWUkaZZHS4RYeuZOYAMQ-4';
