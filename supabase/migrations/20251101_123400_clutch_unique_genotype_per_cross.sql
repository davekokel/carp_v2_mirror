BEGIN;

-- Ensure columns we rely on exist (no-ops if present)
ALTER TABLE public.clutch_instances
  ADD COLUMN IF NOT EXISTS cross_instance_id uuid,
  ADD COLUMN IF NOT EXISTS tank_pair_code   text,
  ADD COLUMN IF NOT EXISTS clutch_genotype_pretty text;

-- Create a partial unique index that matches the conflict target exactly
-- (expression must match byte-for-byte)
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
        ON public.clutch_instances
        (cross_instance_id, lower(btrim(clutch_genotype_pretty)))
        WHERE clutch_genotype_pretty IS NOT NULL
    $ix$;
  END IF;
END $$;

COMMIT;
