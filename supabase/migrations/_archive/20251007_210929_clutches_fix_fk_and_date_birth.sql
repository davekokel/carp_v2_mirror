BEGIN;

-- 1) Ensure date_birth exists
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS date_birth date;

-- 2) If date_fertilized exists, backfill date_birth from it, then drop it
DO $do$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='clutches'
      AND column_name='date_fertilized'
  ) THEN
    UPDATE public.clutches
    SET date_birth = COALESCE(date_birth, date_fertilized);

    ALTER TABLE public.clutches
      DROP COLUMN IF EXISTS date_fertilized;
  END IF;
END
$do$;

-- 3) Add run_id column if missing
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS run_id uuid;

-- 4) Add FK if missing (to cross_plan_runs.id)
DO $do$
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
END
$do$;

-- 5) Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_clutches_run_id ON public.clutches(run_id);

COMMIT;
