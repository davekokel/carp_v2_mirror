BEGIN;

-- 1) Drop the wrong FK from fish_transgene_alleles → transgene_alleles(allele_number)
ALTER TABLE public.fish_transgene_alleles
  DROP CONSTRAINT IF EXISTS fish_transgene_alleles_allele_number_fkey;

-- 2) Drop the wrong unique constraint on transgene_alleles(allele_number)
ALTER TABLE public.transgene_alleles
  DROP CONSTRAINT IF EXISTS transgene_alleles_allele_number_unique;

-- 3) Add the CORRECT FK: (transgene_base_code, allele_number) pair
--    This matches the way we're using ON CONFLICT and how alleles should be modeled.
ALTER TABLE public.fish_transgene_alleles
  ADD CONSTRAINT fish_transgene_alleles_transgene_fk
  FOREIGN KEY (transgene_base_code, allele_number)
  REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
  ON DELETE CASCADE;

COMMIT;
