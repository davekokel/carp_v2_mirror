BEGIN;

COMMENT ON COLUMN public.clutches.legacy_genotype_cross_label
  IS 'LEGACY (v8/v9): pre-v11 free-text genotype label for crosses/clutches. Do not use for new code.';

COMMENT ON COLUMN public.clutches.legacy_genotype_base_codes
  IS 'LEGACY (v8/v9): base-code string for legacy clutches. Superseded by genotypes_v11 + clutch_genotypes_v11.';

COMMENT ON COLUMN public.clutches.legacy_genotype_allele_codes
  IS 'LEGACY (v8/v9): allele-code string for legacy clutches. Superseded by transgene_alleles + genotypes_v11.';

COMMENT ON COLUMN public.clutches.legacy_genotype_pretty
  IS 'LEGACY (v8/v9): pretty genotype label for legacy clutches. Superseded by v11_clutch_label_star.*_tg_style/*.';

COMMENT ON COLUMN public.clutches.legacy_observed_genotype_code
  IS 'LEGACY (v8/v9): observed genotype code for clutches. Superseded by genotypes_v11 + clutch_genotypes_v11.';

COMMIT;
