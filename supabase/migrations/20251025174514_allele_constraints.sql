BEGIN;
ALTER TABLE public.transgene_alleles
  ADD CONSTRAINT IF NOT EXISTS uq_transgene_alleles_base_num UNIQUE (transgene_base_code, allele_number);
COMMIT;
