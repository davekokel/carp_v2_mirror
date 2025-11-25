BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'constructs'
      AND column_name  = 'construct_kind'
  ) THEN
    ALTER TABLE public.constructs
      ADD COLUMN construct_kind text;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'constructs'
      AND column_name  = 'construct_name'
  ) THEN
    ALTER TABLE public.constructs
      ADD COLUMN construct_name text;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'constructs'
      AND column_name  = 'description'
  ) THEN
    ALTER TABLE public.constructs
      ADD COLUMN description text;
  END IF;
END $$;

COMMIT;
