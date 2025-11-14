BEGIN;

ALTER TABLE public.clutch_instances
  ADD COLUMN clutch_genotype text;

COMMIT;
