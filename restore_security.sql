-- Restore security after migration
-- Run this AFTER the migration script completes

-- Remove temporary policy
DROP POLICY IF EXISTS "temp_allow_migration_inserts" ON places;

-- Re-enable RLS
ALTER TABLE places ENABLE ROW LEVEL SECURITY;

-- Ensure the read policy still exists
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

-- Admin policy for modifications
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