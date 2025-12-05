BEGIN;

-- Drop legacy pre-v11 genotype columns from clutches.
-- All modern code should use:
--   - clutches.genotype_v11_id
--   - clutch_genotypes_v11
--   - v11_clutch_star / v11_clutch_label_star

ALTER TABLE public.clutches
  DROP COLUMN IF EXISTS legacy_genotype_cross_label,
  DROP COLUMN IF EXISTS legacy_genotype_base_codes,
  DROP COLUMN IF EXISTS legacy_genotype_allele_codes,
  DROP COLUMN IF EXISTS legacy_genotype_pretty,
  DROP COLUMN IF EXISTS legacy_observed_genotype_code;

COMMIT;
