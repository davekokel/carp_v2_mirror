BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'constructs'
      AND column_name  = 'construct_type'
  ) THEN
    ALTER TABLE public.constructs
      DROP COLUMN construct_type;
  END IF;
END $$;

COMMIT;
