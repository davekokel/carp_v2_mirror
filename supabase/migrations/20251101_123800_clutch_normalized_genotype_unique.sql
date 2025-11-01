BEGIN;

-- 1) Add the stored generated column for conflict arbitration
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='clutch_instances'
      AND column_name='normalized_genotype'
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD COLUMN normalized_genotype text
      GENERATED ALWAYS AS (lower(btrim(clutch_genotype_pretty))) STORED;
  END IF;
END $$;

-- 2) Add a plain UNIQUE CONSTRAINT on (cross_instance_id, normalized_genotype)
--    (Note: unique constraints allow multiple NULLs — that’s fine for optional genotype)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public'
      AND table_name='clutch_instances'
      AND constraint_type='UNIQUE'
      AND constraint_name='uq_clutch_norm_genotype_per_cross'
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT uq_clutch_norm_genotype_per_cross
      UNIQUE (cross_instance_id, normalized_genotype);
  END IF;
END $$;

-- 3) (Optional) Drop the old expression index (arbiter) if present; not needed anymore
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public'
      AND tablename='clutch_instances'
      AND indexname='uq_clutch_genotype_per_cross'
  ) THEN
    EXECUTE 'DROP INDEX public.uq_clutch_genotype_per_cross';
  END IF;
END $$;

COMMIT;
