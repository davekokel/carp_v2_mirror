BEGIN;

-- Ensure columns exist (no-ops if already there)
ALTER TABLE public.clutch_instances
  ADD COLUMN IF NOT EXISTS cross_instance_id uuid,
  ADD COLUMN IF NOT EXISTS tank_pair_code   text,
  ADD COLUMN IF NOT EXISTS clutch_genotype_pretty text;

-- Create the exact arbiter index that matches your ON CONFLICT clause
-- Note: partial on non-NULL genotype; allows one or more NULLs (app limits this)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public'
      AND tablename='clutch_instances'
      AND indexname='uq_clutch_genotype_per_cross'
  ) THEN
    EXECUTE $ix$
      CREATE UNIQUE INDEX uq_clutch_genotype_per_cross
        ON public.clutch_instances (cross_instance_id, lower(btrim(clutch_genotype_pretty)))
        WHERE clutch_genotype_pretty IS NOT NULL
    $ix$;
  END IF;
END $$;

COMMIT;
