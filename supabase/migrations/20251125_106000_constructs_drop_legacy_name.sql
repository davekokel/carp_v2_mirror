BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'constructs'
      AND column_name  = 'name'
  ) THEN
    ALTER TABLE public.constructs
      DROP COLUMN name;
  END IF;
END $$;

COMMIT;
