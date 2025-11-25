BEGIN;

-- Add construct_code if it does not exist yet
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'constructs'
      AND column_name  = 'construct_code'
  ) THEN
    ALTER TABLE public.constructs
      ADD COLUMN construct_code text;
  END IF;
END $$;

-- Make construct_code UNIQUE so ON CONFLICT(..) works
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.constructs'::regclass
      AND conname  = 'constructs_construct_code_key'
  ) THEN
    ALTER TABLE public.constructs
      ADD CONSTRAINT constructs_construct_code_key UNIQUE (construct_code);
  END IF;
END $$;

COMMIT;
