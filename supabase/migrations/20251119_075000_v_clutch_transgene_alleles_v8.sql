BEGIN;

----------------------------------------------------------------------
-- v_clutch_transgene_alleles
--
-- For each clutch, derive the allele set implied by its genotype:
--   - Prefer cl.observed_genotype_code when present
--   - Otherwise fall back to cr.expected_genotype_code
--
-- This view is read-only and depends on:
--   - clutches (observed_genotype_code, cross_id)
--   - crosses (expected_genotype_code)
--   - genotype_transgene_alleles (genotype_code → alleles)
----------------------------------------------------------------------

DROP VIEW IF EXISTS public.v_clutch_transgene_alleles CASCADE;

CREATE VIEW public.v_clutch_transgene_alleles AS
SELECT
  cl.id                         AS clutch_id,
  cl.clutch_code,
  cl.clutch_date,
  COALESCE(cl.observed_genotype_code, cr.expected_genotype_code)
                                AS genotype_code,
  gta.transgene_base_code,
  gta.allele_number,
  gta.zygosity
FROM public.clutches cl
LEFT JOIN public.crosses cr
  ON cr.id = cl.cross_id
JOIN public.genotype_transgene_alleles gta
  ON gta.genotype_code =
     COALESCE(cl.observed_genotype_code, cr.expected_genotype_code);

COMMIT;
