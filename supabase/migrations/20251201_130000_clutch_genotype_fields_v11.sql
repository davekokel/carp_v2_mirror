BEGIN;

ALTER TABLE public.clutches
  ADD COLUMN genotype_base_codes text,
  ADD COLUMN genotype_allele_codes text;

COMMIT;
