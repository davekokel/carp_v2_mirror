-- Drop the partial unique index if it exists (it won't be used by ON CONFLICT (column))
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='cross_instances'
      AND indexname='uq_cross_idempotency_key'
  ) THEN
    EXECUTE 'DROP INDEX public.uq_cross_idempotency_key';
  END IF;
END $$;

-- Ensure the column exists
ALTER TABLE public.cross_instances
  ADD COLUMN IF NOT EXISTS idempotency_key text;

-- Add a proper UNIQUE constraint (permits multiple NULLs in Postgres)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='uq_cross_idempotency_key'
      AND conrelid='public.cross_instances'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_instances
             ADD CONSTRAINT uq_cross_idempotency_key
             UNIQUE (idempotency_key)';
  END IF;
END $$;
