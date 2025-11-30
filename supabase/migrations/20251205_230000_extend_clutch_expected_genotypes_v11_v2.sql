BEGIN;

-- Add all legacy-style columns the v11_seed_clutch_expected_markers_from_v9.py script expects.
ALTER TABLE public.clutch_expected_genotypes_v11
  ADD COLUMN IF NOT EXISTS treatment_code text,
  ADD COLUMN IF NOT EXISTS genotype_basecode_code text,
  ADD COLUMN IF NOT EXISTS genotype_transgene_allele_code text,
  ADD COLUMN IF NOT EXISTS treatments_and_transgenes text,
  ADD COLUMN IF NOT EXISTS zygocity_vector text,
  ADD COLUMN IF NOT EXISTS expected_fraction numeric,
  ADD COLUMN IF NOT EXISTS expected_percent_label text,
  ADD COLUMN IF NOT EXISTS is_enabled boolean DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS label text;

COMMIT;
