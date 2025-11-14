BEGIN;

ALTER TABLE public.clutch_instances
  DROP COLUMN IF EXISTS clutch_genotype;

COMMIT;
