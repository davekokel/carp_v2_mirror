BEGIN;

-- Rebuild v_clutch_instances with the same columns as before.
-- Only change: derive clutch_genotype_codes as a semicolon-joined offspring list
-- from b.clutch_genotype_pretty (tokens Tg(...), order-preserved, DISTINCT).

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
    COALESCE(NULLIF(TRIM(BOTH FROM ct.treatment_code_norm), ''), NULLIF(TRIM(BOTH FROM ct.treatment_code), '')) AS t_code,
    NULLIF(TRIM(BOTH FROM ct.treatment_name), '') AS t_name
  FROM ci_map m
  JOIN public.join_clutch_treatments ct
    ON ct.clutch_instance_id = m.clutch_instance_id
),
tx_roll AS (
  SELECT
    tx.clutch_code,
    string_agg(DISTINCT tx.t_code, ';' ORDER BY tx.t_code) AS clutch_treatments_codes,
    string_agg(DISTINCT tx.t_name, ';' ORDER BY tx.t_name) AS clutch_treatments_names
  FROM tx
  GROUP BY tx.clutch_code
),
tx_fusion AS (
  SELECT
    tx.clutch_code,
    string_agg(DISTINCT public.plasmid_fusion_label(tx.t_code), ';'
               ORDER BY public.plasmid_fusion_label(tx.t_code)) AS clutch_treatments_fusions
  FROM tx
  WHERE tx.t_code IS NOT NULL
  GROUP BY tx.clutch_code
),
-- derive offspring genotype codes from the pretty string (Tg(...) tokens → ';'-joined)
geno_codes AS (
  SELECT
    b.clutch_code,
    (regexp_matches(b.clutch_genotype_pretty, 'Tg\(([^)]+)\)[^;×,]*', 'g'))[1] AS p_code
  FROM base b
),
geno_codes_join AS (
  SELECT
    g.clutch_code,
    string_agg(DISTINCT g.p_code, ';' ORDER BY g.p_code) AS clutch_genotype_codes
  FROM geno_codes g
  GROUP BY g.clutch_code
),
geno_fusions AS (
  SELECT
    g.clutch_code,
    public.plasmid_fusion_label(g.p_code) AS fusion_label
  FROM geno_codes g
),
geno_roll AS (
  SELECT
    gf.clutch_code,
    string_agg(DISTINCT gf.fusion_label, ';' ORDER BY gf.fusion_label) AS clutch_genotype_fusions
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

  -- ✅ fixed: semicolon offspring list
  gcj.clutch_genotype_codes,

  tr.clutch_treatments_codes,
  tr.clutch_treatments_names,
  tf.clutch_treatments_fusions,
  gr.clutch_genotype_fusions,

  -- keep original lineage aliases/names, but use the corrected codes source
  CASE
    WHEN NULLIF(tr.clutch_treatments_codes,'') IS NOT NULL
      THEN tr.clutch_treatments_codes || ' > ' || gcj.clutch_genotype_codes
    ELSE gcj.clutch_genotype_codes
  END AS clutch_lineage_pretty,

  CASE
    WHEN NULLIF(tf.clutch_treatments_fusions,'') IS NOT NULL
      THEN tf.clutch_treatments_fusions || ' > ' || gcj.clutch_genotype_codes
    ELSE gcj.clutch_genotype_codes
  END AS clutch_lineage_fusions_pretty,

  CASE
    WHEN NULLIF(tf.clutch_treatments_fusions,'') IS NOT NULL
      THEN tf.clutch_treatments_fusions || ' > ' ||
           COALESCE(gr.clutch_genotype_fusions, gcj.clutch_genotype_codes)
    ELSE COALESCE(gr.clutch_genotype_fusions, gcj.clutch_genotype_codes)
  END AS clutch_lineage_full_fusions_pretty

FROM base b
LEFT JOIN tx_roll        tr  ON tr.clutch_code  = b.clutch_code
LEFT JOIN tx_fusion      tf  ON tf.clutch_code  = b.clutch_code
LEFT JOIN geno_codes_join gcj ON gcj.clutch_code = b.clutch_code
LEFT JOIN geno_roll      gr  ON gr.clutch_code  = b.clutch_code;

COMMIT;
