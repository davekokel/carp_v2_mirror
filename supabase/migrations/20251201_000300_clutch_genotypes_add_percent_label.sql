BEGIN;

ALTER TABLE public.clutch_genotypes_v11
  ADD COLUMN IF NOT EXISTS expected_percent_label text;

COMMENT ON COLUMN public.clutch_genotypes_v11.expected_percent_label IS
  'Human-readable percent label (e.g. 25%, 50%) corresponding to expected_fraction; optional.';

COMMIT;
