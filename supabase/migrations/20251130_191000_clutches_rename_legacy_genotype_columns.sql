BEGIN;

-- Legacy text-ish genotype fields → make them clearly legacy

ALTER TABLE public.clutches
  RENAME COLUMN genotype_cross_label       TO legacy_genotype_cross_label;

ALTER TABLE public.clutches
  RENAME COLUMN genotype_base_codes       TO legacy_genotype_base_codes;

ALTER TABLE public.clutches
  RENAME COLUMN genotype_allele_codes     TO legacy_genotype_allele_codes;

ALTER TABLE public.clutches
  RENAME COLUMN genotype_pretty           TO legacy_genotype_pretty;

ALTER TABLE public.clutches
  RENAME COLUMN observed_genotype_code    TO legacy_observed_genotype_code;

-- genotype_v11_id stays as-is and is the canonical FK → genotypes_v11(id)

COMMIT;
