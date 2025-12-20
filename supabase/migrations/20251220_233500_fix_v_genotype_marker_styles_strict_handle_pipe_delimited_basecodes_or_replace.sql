BEGIN;

CREATE OR REPLACE VIEW public.v_genotype_marker_styles_strict AS
WITH g AS (
  SELECT
    gv.genotype_code,
    NULLIF(btrim(gv.genotype_pretty), '') AS genotype_tg_style,
    gv.genotype_basecodes
  FROM public.genotypes_v11 gv
  WHERE coalesce(btrim(gv.genotype_code), '') <> ''
),
tok AS (
  SELECT
    g.genotype_code,
    g.genotype_tg_style,
    btrim(t) AS raw_tok
  FROM g
  CROSS JOIN LATERAL regexp_split_to_table(replace(coalesce(g.genotype_basecodes, ''), '|', ';'), '\s*;\s*') AS t
  WHERE coalesce(btrim(t), '') <> ''
),
base AS (
  SELECT
    genotype_code,
    genotype_tg_style,
    lower(m[1]) AS base_code
  FROM tok
  CROSS JOIN LATERAL regexp_matches(raw_tok, '^\s*([a-z0-9-]+)(?:\s*:\s*\d+)?\s*$', 'i') AS m
),
joined AS (
  SELECT
    b.genotype_code,
    b.genotype_tg_style,
    vcms.fluortag_style,
    vcms.fluororganelle_style
  FROM base b
  LEFT JOIN public.v_construct_marker_styles vcms
    ON vcms.base_code = b.base_code
),
agg AS (
  SELECT
    genotype_code,
    max(genotype_tg_style) AS genotype_tg_style,
    (
      SELECT string_agg(x, '; ' ORDER BY x)
      FROM (
        SELECT DISTINCT NULLIF(btrim(fluortag_style), '') AS x
        FROM joined j2
        WHERE j2.genotype_code = j.genotype_code
      ) s
      WHERE x IS NOT NULL
    ) AS genotype_fluortag_style,
    (
      SELECT string_agg(x, '; ' ORDER BY x)
      FROM (
        SELECT DISTINCT NULLIF(btrim(fluororganelle_style), '') AS x
        FROM joined j2
        WHERE j2.genotype_code = j.genotype_code
      ) s
      WHERE x IS NOT NULL
    ) AS genotype_fluororganelle_style
  FROM joined j
  GROUP BY genotype_code
)
SELECT
  genotype_code,
  genotype_tg_style,
  genotype_fluortag_style,
  genotype_fluororganelle_style
FROM agg;

COMMIT;
