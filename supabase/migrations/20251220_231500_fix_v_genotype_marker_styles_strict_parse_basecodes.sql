BEGIN;

CREATE OR REPLACE VIEW public.v_genotype_marker_styles_strict AS
WITH g AS (
  SELECT
    gv.genotype_code,
    gv.genotype_basecodes
  FROM public.genotypes_v11 gv
  WHERE coalesce(btrim(gv.genotype_basecodes), '') <> ''
),
tok AS (
  SELECT
    g.genotype_code,
    btrim(x.tok) AS tok
  FROM g
  CROSS JOIN LATERAL regexp_split_to_table(g.genotype_basecodes, '\s*;\s*') AS x(tok)
),
parts AS (
  SELECT
    t.genotype_code,
    lower(m[1]) AS base_code
  FROM tok t
  CROSS JOIN LATERAL regexp_matches(t.tok, '^\s*([a-z0-9-]+)\s*:\s*\d+\s*$', 'i') AS m
),
joined AS (
  SELECT
    p.genotype_code,
    vcms.fluortag_style,
    vcms.fluororganelle_style
  FROM parts p
  JOIN public.v_construct_marker_styles vcms
    ON vcms.base_code = p.base_code
),
agg AS (
  SELECT
    genotype_code,
    NULLIF(string_agg(DISTINCT btrim(fluortag_style), '; ' ORDER BY btrim(fluortag_style)), '') AS genotype_fluortag_style,
    NULLIF(string_agg(DISTINCT btrim(fluororganelle_style), '; ' ORDER BY btrim(fluororganelle_style)), '') AS genotype_fluororganelle_style
  FROM joined
  WHERE
    coalesce(btrim(fluortag_style), '') <> ''
    OR coalesce(btrim(fluororganelle_style), '') <> ''
  GROUP BY genotype_code
)
SELECT
  g.genotype_code,
  g.genotype_basecodes AS genotype_tg_style,
  a.genotype_fluortag_style,
  a.genotype_fluororganelle_style
FROM g
LEFT JOIN agg a USING (genotype_code);

COMMIT;
