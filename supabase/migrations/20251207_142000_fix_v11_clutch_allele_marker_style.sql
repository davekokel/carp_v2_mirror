BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_allele_marker_style;

CREATE VIEW public.v11_clutch_allele_marker_style AS
WITH allele_rollup AS (
  SELECT
    clutch_code,
    STRING_AGG(
      CASE
        WHEN allele_nickname IS NOT NULL AND allele_nickname <> ''
          THEN transgene_base_code || '(' || allele_nickname || ')'
        ELSE transgene_base_code
      END,
      '; ' ORDER BY transgene_base_code, allele_nickname
    ) AS genotype_basecode_allele_style
  FROM (
    -- Deduplicate mother/father rows at the allele level
    SELECT DISTINCT
      clutch_code,
      transgene_base_code,
      allele_nickname
    FROM raw.legacy_clutch_transgene_alleles_v9
    WHERE has_transgene_allele IS TRUE
  ) t
  GROUP BY clutch_code
)
SELECT
  c.clutch_code,
  ar.genotype_basecode_allele_style
FROM public.clutches c
LEFT JOIN allele_rollup ar
  ON ar.clutch_code = c.clutch_code;

COMMENT ON VIEW public.v11_clutch_allele_marker_style IS
'Legacy-only helper: one row per clutch with UNIQUE genotype_basecode_allele_style from raw.legacy_clutch_transgene_alleles_v9, rolled as basecode(nickname) tokens across both parents.';

COMMIT;
