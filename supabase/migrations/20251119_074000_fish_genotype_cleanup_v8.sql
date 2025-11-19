BEGIN;

----------------------------------------------------------------------
-- v8: Remove join_fish_transgene_alleles as a table and replace it
--     with a derived view based on genotype_transgene_alleles.
--
-- Canonical chain:
--   transgenes → transgene_alleles
--             → genotype_transgene_alleles
--             → genotypes
--             → fish_instance.standard_genotype_code
----------------------------------------------------------------------

-- 1. Drop any existing view with that name (if we created one earlier)
DROP VIEW IF EXISTS public.v_fish_transgene_alleles CASCADE;

-- 2. Drop the legacy table, if it exists
DROP TABLE IF EXISTS public.join_fish_transgene_alleles CASCADE;

-- 3. Create the derived view:
--    For each fish, show the alleles implied by its standard_genotype_code.
CREATE VIEW public.v_fish_transgene_alleles AS
SELECT
  f.id                   AS fish_id,
  f.fish_code,
  f.standard_genotype_code,
  gta.transgene_base_code,
  gta.allele_number,
  gta.zygosity
FROM public.fish_instance f
JOIN public.genotype_transgene_alleles gta
  ON gta.genotype_code = f.standard_genotype_code;

COMMIT;
