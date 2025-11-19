BEGIN;

----------------------------------------------------------------------
-- v8: Clean up genotype ↔ allele joins
--
-- Canonical join: genotype_transgene_alleles
-- Legacy table:   join_genotype_transgene_alleles
--
-- Strategy:
--   1) Drop the legacy table if it still exists.
--   2) Provide a compatibility VIEW with the old name that simply
--      selects from genotype_transgene_alleles.
----------------------------------------------------------------------

-- 1. Drop legacy table (if any)
DROP TABLE IF EXISTS public.join_genotype_transgene_alleles CASCADE;

-- 2. Compatibility VIEW for any old code still using the legacy name
DROP VIEW IF EXISTS public.join_genotype_transgene_alleles CASCADE;

CREATE VIEW public.join_genotype_transgene_alleles AS
SELECT
  gta.genotype_code,
  gta.transgene_base_code,
  gta.allele_number,
  gta.zygosity
FROM public.genotype_transgene_alleles gta;

COMMIT;
