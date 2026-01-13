-- Temporarily allow migration inserts
-- Run this BEFORE running the migration script

-- Temporarily disable RLS for migration
ALTER TABLE places DISABLE ROW LEVEL SECURITY;

-- Allow all inserts during migration (will be removed after)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policy
    WHERE polname = 'temp_allow_migration_inserts'
      AND polrelid = 'public.places'::regclass
  ) THEN
    CREATE POLICY "temp_allow_migration_inserts"
      ON public.places
      FOR INSERT
      TO public
      WITH CHECK (true);
  END IF;
END
$$;