BEGIN;

ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS genotype_base_codes    text,
  ADD COLUMN IF NOT EXISTS genotype_allele_codes  text,
  ADD COLUMN IF NOT EXISTS genotype_pretty        text,
  ADD COLUMN IF NOT EXISTS observed_genotype_code text;

COMMIT;
