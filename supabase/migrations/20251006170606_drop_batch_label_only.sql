BEGIN;

-- Drop the batch_label column if it still exists
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish_seed_batches_map'
      AND column_name='batch_label'
  ) THEN
    ALTER TABLE public.fish_seed_batches_map DROP COLUMN batch_label;
  END IF;
END$$;

COMMIT;
