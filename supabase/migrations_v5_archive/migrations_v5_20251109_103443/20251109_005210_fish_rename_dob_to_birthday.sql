BEGIN;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='dob'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='birthday'
  ) THEN
    ALTER TABLE public.fish RENAME COLUMN dob TO birthday;
  END IF;
END$$;
COMMIT;
