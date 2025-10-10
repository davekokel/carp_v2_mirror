BEGIN;

-- Ensure date_birth exists
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS date_birth date;

-- If you still have date_fertilized with data, migrate it once
UPDATE public.clutches
SET date_birth = COALESCE(date_birth, date_fertilized)
WHERE date_birth IS NULL;

-- Drop date_fertilized (we'll use only date_birth going forward)
ALTER TABLE public.clutches
  DROP COLUMN IF EXISTS date_fertilized;

-- Add run_id column (FK to cross_plan_runs) if missing
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS run_id uuid;

-- Add the FK if it doesn't already exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints
    WHERE table_schema='public'
      AND table_name='clutches'
      AND constraint_type='FOREIGN KEY'
      AND constraint_name='clutches_run_id_fkey'
  ) THEN
    ALTER TABLE public.clutches
      ADD CONSTRAINT clutches_run_id_fkey
      FOREIGN KEY (run_id) REFERENCES public.cross_plan_runs(id)
      ON DELETE SET NULL;
  END IF;
END$$;

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_clutches_run_id ON public.clutches(run_id);

COMMIT;
