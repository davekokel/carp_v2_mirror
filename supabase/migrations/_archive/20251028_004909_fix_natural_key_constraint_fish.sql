-- If we previously created a functional index, drop it (safe if absent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='uq_fish_seed_name_dob_idx'
  ) THEN
    DROP INDEX public.uq_fish_seed_name_dob_idx;
  END IF;
END$$;

-- Normalize any existing NULLs (on a clean rebuild there won't be any)
UPDATE public.fish SET seed_batch_id = '' WHERE seed_batch_id IS NULL;
UPDATE public.fish SET name          = '' WHERE name          IS NULL;
-- If you expect every fish to have a birthday (CSV enforces it), make it NOT NULL too:
-- UPDATE public.fish SET date_birth   = '1900-01-01' WHERE date_birth IS NULL;

-- Make the natural key columns NOT NULL (adjust if you want date_birth nullable)
ALTER TABLE public.fish
  ALTER COLUMN seed_batch_id SET DEFAULT '',
  ALTER COLUMN seed_batch_id SET NOT NULL,
  ALTER COLUMN name          SET DEFAULT '',
  ALTER COLUMN name          SET NOT NULL;
  -- If you require DOB: ALTER COLUMN date_birth SET NOT NULL;

-- Create a real unique constraint on the columns (no expressions)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c
    JOIN pg_class rel ON rel.oid=c.conrelid
    JOIN pg_namespace n ON n.oid=rel.relnamespace
    WHERE n.nspname='public' AND rel.relname='fish'
      AND c.contype='u' AND c.conname='uq_fish_seed_name_dob'
  ) THEN
    ALTER TABLE public.fish
      ADD CONSTRAINT uq_fish_seed_name_dob
      UNIQUE (seed_batch_id, name, date_birth);
  END IF;
END$$;
