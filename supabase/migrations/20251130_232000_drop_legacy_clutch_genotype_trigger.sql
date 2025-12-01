BEGIN;

DROP TRIGGER IF EXISTS trg_frontfill_clutch_genotype_on_imaging
  ON public.imaging_clutch_memberships;

DROP FUNCTION IF EXISTS public.fn_frontfill_clutch_genotype_on_imaging() CASCADE;

COMMIT;
