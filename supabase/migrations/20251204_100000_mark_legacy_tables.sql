BEGIN;

-- Mark legacy tables clearly so v11 "current world" stands out.

COMMENT ON TABLE public.clutch_expected_genotypes_v11_legacy IS
  'LEGACY: transitional table from v9/v10 expected genotype pipeline. \
   Kept only for debugging/comparison; v11 uses clutch_genotypes_v11 and related views.';

-- If you later identify more legacy tables/views you want to tag in the same way,
-- add more COMMENT ON statements here or in follow-up migrations.

COMMIT;
