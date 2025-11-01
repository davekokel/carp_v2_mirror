BEGIN;

-- Drop the "exactly one clutch per cross" unique index if we created it
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='clutch_instances'
      AND indexname='uq_clutch_per_cross'
  ) THEN
    EXECUTE 'DROP INDEX public.uq_clutch_per_cross';
  END IF;
END $$;

-- Drop the AFTER INSERT safety trigger on crosses if present
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_trigger
    WHERE tgrelid = 'public.crosses'::regclass
      AND tgname = 'trg_crosses_ensure_clutch'
  ) THEN
    EXECUTE 'DROP TRIGGER trg_crosses_ensure_clutch ON public.crosses';
  END IF;

  -- Drop the function too (ignore if missing)
  IF EXISTS (
    SELECT 1 FROM pg_proc
    WHERE pronamespace='public'::regnamespace AND proname='ensure_clutch_after_cross'
  ) THEN
    EXECUTE 'DROP FUNCTION public.ensure_clutch_after_cross()';
  END IF;
END $$;

-- Ensure clutch_instances has the fields we rely on
ALTER TABLE public.clutch_instances
  ADD COLUMN IF NOT EXISTS cross_instance_id uuid,
  ADD COLUMN IF NOT EXISTS tank_pair_code   text,
  ADD COLUMN IF NOT EXISTS clutch_genotype_pretty text;

-- Partial unique: disallow duplicate (cross, genotype) for non-NULL genotype (case/space-insensitive)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='clutch_instances'
      AND indexname='uq_clutch_unique_genotype_per_cross'
  ) THEN
    EXECUTE $ix$
      CREATE UNIQUE INDEX uq_clutch_unique_genotype_per_cross
        ON public.clutch_instances (cross_instance_id, lower(btrim(clutch_genotype_pretty)))
        WHERE clutch_genotype_pretty IS NOT NULL
    $ix$;
  END IF;
END $$;

COMMIT;
