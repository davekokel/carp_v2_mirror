BEGIN;

CREATE OR REPLACE VIEW public.v_genotype_marker_styles_strict AS
WITH g AS (
  SELECT
    gv.genotype_code,
    NULLIF(btrim(gv.genotype_basecodes), '') AS genotype_basecodes
  FROM public.genotypes_v11 gv
  WHERE COALESCE(btrim(gv.genotype_code), '') <> ''
),
bases AS (
  SELECT
    g.genotype_code,
    lower(m[1]) AS base_code
  FROM g
  CROSS JOIN LATERAL regexp_matches(g.genotype_basecodes, 'tg\(([^)]+)\)', 'g') AS m
),
agg AS (
  SELECT
    b.genotype_code,
    string_agg(DISTINCT vcms.fluortag_style, '; ' ORDER BY vcms.fluortag_style)
      FILTER (WHERE vcms.fluortag_style IS NOT NULL AND btrim(vcms.fluortag_style) <> '') AS genotype_fluortag_style,
    string_agg(DISTINCT vcms.fluororganelle_style, '; ' ORDER BY vcms.fluororganelle_style)
      FILTER (WHERE vcms.fluororganelle_style IS NOT NULL AND btrim(vcms.fluororganelle_style) <> '') AS genotype_fluororganelle_style
  FROM bases b
  LEFT JOIN public.v_construct_marker_styles vcms
    ON vcms.base_code = b.base_code
  GROUP BY b.genotype_code
)
SELECT
  g.genotype_code,
  g.genotype_basecodes AS genotype_tg_style,
  a.genotype_fluortag_style,
  a.genotype_fluororganelle_style
FROM g
LEFT JOIN agg a USING (genotype_code);

COMMIT;
