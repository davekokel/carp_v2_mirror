BEGIN;

-- v_clutches_overview depends on clutch_genotype currently, so drop the view first.
DROP VIEW IF EXISTS public.v_clutches_overview;

-- Remove the inline genotype column from clutch_instances; canonical store is clutch_expected_genotypes.
ALTER TABLE public.clutch_instances
  DROP COLUMN IF EXISTS clutch_genotype;

COMMIT;
