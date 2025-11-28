BEGIN;

ALTER TABLE public.clutch_expected_genotypes_v11
  ADD COLUMN IF NOT EXISTS label text;

COMMIT;
