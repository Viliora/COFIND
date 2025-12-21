-- ============================================
-- ADD updated_at COLUMN TO review_replies TABLE
-- ============================================
-- This allows tracking when a reply was last edited

-- Add updated_at column if it doesn't exist
ALTER TABLE review_replies 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Set existing rows' updated_at to their created_at
UPDATE review_replies 
SET updated_at = created_at 
WHERE updated_at IS NULL;

-- Add trigger to auto-update updated_at on UPDATE
CREATE OR REPLACE FUNCTION update_reply_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if exists (untuk re-run safety)
DROP TRIGGER IF EXISTS set_reply_updated_at ON review_replies;

-- Create trigger
CREATE TRIGGER set_reply_updated_at
  BEFORE UPDATE ON review_replies
  FOR EACH ROW
  EXECUTE FUNCTION update_reply_updated_at();

-- Verify the column was added
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'review_replies' 
  AND column_name = 'updated_at';

-- Success message
DO $$
BEGIN
  RAISE NOTICE '✅ Column updated_at added to review_replies table!';
  RAISE NOTICE '✅ Trigger set_reply_updated_at created!';
  RAISE NOTICE '✅ Existing replies updated with created_at as updated_at!';
END $$;

