BEGIN;

-- Recreate v_clutch_instances with identical shape, but btrim the extracted tokens/codes
-- to avoid trailing spaces before the '; ' joiner.

CREATE OR REPLACE VIEW public.v_clutch_instances AS
WITH
base AS (
  SELECT
    v.clutch_code,
    v.clutch_birthday,
    v.cross_name_pretty,
    v.clutch_name,
    v.clutch_genotype_pretty,
    v.clutch_strain_pretty,
    v.treatments_count_effective,
    v.treatments_pretty_effective,
    v.genotype_treatment_rollup_effective,
    v.created_by_instance,
    v.created_at_instance
  FROM public.v_clutch_instances_base v
),
ci_map AS (
  SELECT
    ci.id  AS clutch_instance_id,
    ci.clutch_instance_code AS clutch_code
  FROM public.clutch_instances ci
),
tx AS (
  SELECT
    m.clutch_code,
    COALESCE(NULLIF(TRIM(BOTH FROM ct.treatment_code_norm), ''),
             NULLIF(TRIM(BOTH FROM ct.treatment_code), '')) AS t_code,
    NULLIF(TRIM(BOTH FROM ct.treatment_name), '') AS t_name
  FROM ci_map m
  JOIN public.join_clutch_treatments ct
    ON ct.clutch_instance_id = m.clutch_instance_id
),
tx_roll AS (
  SELECT
    tx.clutch_code,
    string_agg(DISTINCT tx.t_code, '; ' ORDER BY tx.t_code) AS clutch_treatments_codes,
    string_agg(DISTINCT tx.t_name, '; ' ORDER BY tx.t_name) AS clutch_treatments_names
  FROM tx
  GROUP BY tx.clutch_code
),
tx_fusion AS (
  SELECT
    tx.clutch_code,
    string_agg(
      DISTINCT public.plasmid_fusion_label(tx.t_code),
      '; ' ORDER BY public.plasmid_fusion_label(tx.t_code)
    ) AS clutch_treatments_fusions
  FROM tx
  WHERE tx.t_code IS NOT NULL
  GROUP BY tx.clutch_code
),

-- Extract tokens (case-insensitive), keep ordinal
geno_tokens AS (
  SELECT
    b.clutch_code,
    m.ord::int                                 AS ord,
    m.m[1]                                     AS tg_full_raw,
    (regexp_matches(m.m[1], '\(([^)]+)\)'))[1] AS p_code_raw
  FROM base b,
       regexp_matches(b.clutch_genotype_pretty, 'Tg\([^)]+\)[^;×,]*', 'gi')
       WITH ORDINALITY AS m(m, ord)
),

-- De-dupe but keep first-seen order; TRIM tokens/codes here
codes_distinct AS (
  SELECT clutch_code, btrim(p_code_raw) AS p_code, MIN(ord) AS ord
  FROM geno_tokens
  WHERE p_code_raw IS NOT NULL AND btrim(p_code_raw) <> ''
  GROUP BY clutch_code, btrim(p_code_raw)
),
tokens_distinct AS (
  SELECT clutch_code, btrim(tg_full_raw) AS tg_full, MIN(ord) AS ord
  FROM geno_tokens
  WHERE btrim(tg_full_raw) <> ''
  GROUP BY clutch_code, btrim(tg_full_raw)
),

-- Offspring genotype (codes) ; separated with a space
geno_codes_join AS (
  SELECT clutch_code,
         string_agg(p_code, '; ' ORDER BY ord) AS clutch_genotype_codes
  FROM codes_distinct
  GROUP BY clutch_code
),

-- Offspring genotype (full Tg tokens) ; separated with a space
geno_tokens_join AS (
  SELECT clutch_code,
         string_agg(tg_full, '; ' ORDER BY ord) AS clutch_genotype_tokens
  FROM tokens_distinct
  GROUP BY clutch_code
),

-- Fusions derived from codes
geno_fusions AS (
  SELECT
    t.clutch_code,
    public.plasmid_fusion_label(t.p_code) AS fusion_label
  FROM codes_distinct t
),
geno_roll AS (
  SELECT
    gf.clutch_code,
    string_agg(DISTINCT gf.fusion_label, '; ' ORDER BY gf.fusion_label) AS clutch_genotype_fusions
  FROM geno_fusions gf
  GROUP BY gf.clutch_code
)

SELECT
  b.clutch_code,
  b.clutch_birthday,
  b.cross_name_pretty,
  b.clutch_name,
  b.clutch_genotype_pretty,
  b.clutch_strain_pretty,
  b.treatments_count_effective,
  b.treatments_pretty_effective,
  b.genotype_treatment_rollup_effective,
  b.created_by_instance,
  b.created_at_instance,

  -- Offspring codes (semicolon + space) — now trimmed tokens
  gcj.clutch_genotype_codes,

  tr.clutch_treatments_codes,
  tr.clutch_treatments_names,
  tf.clutch_treatments_fusions,

  -- Offspring fusions (semicolon + space)
  gr.clutch_genotype_fusions,

  -- Full Tg tokens (semicolon + space) — now trimmed tokens
  gtj.clutch_genotype_tokens,

  -- Lineage (unchanged names)
  CASE
    WHEN NULLIF(tr.clutch_treatments_codes, '') IS NOT NULL
      THEN tr.clutch_treatments_codes || ' > ' || gcj.clutch_genotype_codes
    ELSE gcj.clutch_genotype_codes
  END AS clutch_lineage_pretty,

  CASE
    WHEN NULLIF(tf.clutch_treatments_fusions, '') IS NOT NULL
      THEN tf.clutch_treatments_fusions || ' > ' || gcj.clutch_genotype_codes
    ELSE gcj.clutch_genotype_codes
  END AS clutch_lineage_fusions_pretty,

  CASE
    WHEN NULLIF(tf.clutch_treatments_fusions, '') IS NOT NULL
      THEN tf.clutch_treatments_fusions || ' > ' ||
           COALESCE(gr.clutch_genotype_fusions, gcj.clutch_genotype_codes)
    ELSE COALESCE(gr.clutch_genotype_fusions, gcj.clutch_genotype_codes)
  END AS clutch_lineage_full_fusions_pretty

FROM base b
LEFT JOIN tx_roll         tr  ON tr.clutch_code  = b.clutch_code
LEFT JOIN tx_fusion       tf  ON tf.clutch_code  = b.clutch_code
LEFT JOIN geno_codes_join gcj ON gcj.clutch_code = b.clutch_code
LEFT JOIN geno_tokens_join gtj ON gtj.clutch_code = b.clutch_code
LEFT JOIN geno_roll       gr  ON gr.clutch_code  = b.clutch_code;

COMMIT;
