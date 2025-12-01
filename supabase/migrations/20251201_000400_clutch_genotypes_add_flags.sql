BEGIN;

ALTER TABLE public.clutch_genotypes_v11
  ADD COLUMN IF NOT EXISTS expected_fraction numeric,
  ADD COLUMN IF NOT EXISTS expected_percent_label text,
  ADD COLUMN IF NOT EXISTS is_enabled boolean DEFAULT true;

COMMENT ON COLUMN public.clutch_genotypes_v11.expected_fraction IS
  'Expected fraction of embryos with this genotype (0–1), optional.';
COMMENT ON COLUMN public.clutch_genotypes_v11.expected_percent_label IS
  'Human-readable percent label (e.g. 25%, 50%) corresponding to expected_fraction; optional.';
COMMENT ON COLUMN public.clutch_genotypes_v11.is_enabled IS
  'Whether this expected genotype is currently active/enabled for the clutch.';

COMMIT;
