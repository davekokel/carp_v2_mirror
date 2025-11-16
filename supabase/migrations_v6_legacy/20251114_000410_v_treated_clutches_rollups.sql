BEGIN;

DROP VIEW IF EXISTS public.v_treated_clutches_overview;

CREATE VIEW public.v_treated_clutches_overview AS
WITH base AS (
  SELECT
    tc.id                  AS treated_clutch_id,
    tc.treated_clutch_code,
    tc.clutch_instance_id,
    tc.created_at          AS group_created_at
  FROM public.treated_clutches tc
),

tx_raw AS (
  SELECT
    tc.treated_clutch_code,
    tc.clutch_instance_id,
    tc.created_at          AS group_created_at,
    t.treat_code,
    COALESCE(t.treat_text, t.treat_code) AS treat_name
  FROM public.treated_clutches tc
  LEFT JOIN public.join_clutch_treatments jct ON jct.treated_clutch_id = tc.id
  LEFT JOIN public.treatments           t    ON t.id = jct.treatment_id
),

tx_distinct AS (
  SELECT DISTINCT
    treated_clutch_code,
    clutch_instance_id,
    group_created_at,
    treat_code,
    treat_name
  FROM tx_raw
),

grp AS (
  SELECT
    treated_clutch_code,
    clutch_instance_id,
    MIN(group_created_at) AS group_created_at,
    COUNT(treat_code)     AS treatments_count_group,
    COALESCE(string_agg(treat_code, '+' ORDER BY treat_code), '')   AS treatments_codes_group,
    COALESCE(string_agg(treat_name, ' + ' ORDER BY treat_name), '') AS treatments_names_group
  FROM tx_distinct
  GROUP BY treated_clutch_code, clutch_instance_id
),

vc AS (
  SELECT
    clutch_instance_id,
    clutch_code,
    clutch_date           AS clutch_birthday,
    cross_code,
    cross_date,
    mom_fish_code,
    dad_fish_code,
    mom_genotype,
    dad_genotype,
    mom_fusions,
    dad_fusions,
    clutch_genotype,
    clutch_genotype_pretty,
    genotype_codes_rollup,
    allele_names_rollup,
    genotype_fusions_rollup
  FROM public.v_clutches_overview
),

tx_sources AS (
  SELECT
    tc.treated_clutch_code,
    t.kind_code,
    t.treat_code
  FROM public.treated_clutches       tc
  JOIN public.join_clutch_treatments jct ON jct.treated_clutch_id = tc.id
  JOIN public.treatments             t   ON t.id = jct.treatment_id
),

tx_plasmid AS (
  SELECT DISTINCT
    ts.treated_clutch_code,
    COALESCE(fl.fluor_code, '') AS fluor_token
  FROM tx_sources ts
  JOIN public.plasmids          p   ON ts.kind_code = 'plasmid' AND p.code = ts.treat_code
  JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
  JOIN public.fusions           f   ON f.id = jpf.fusion_id
  LEFT JOIN public.fluors       fl  ON fl.id = f.fluor_id
  WHERE COALESCE(fl.fluor_code,'') <> ''
),

tx_rna AS (
  SELECT DISTINCT
    ts.treated_clutch_code,
    CASE
      WHEN COALESCE(fl.fluor_code,'') <> '' AND COALESCE(tg.tag_code,'') <> '' THEN
        fl.fluor_code || ':' || tg.tag_code ||
        CASE WHEN f.tag_pos IS NOT NULL AND f.tag_pos <> '' THEN '(' || f.tag_pos || ')' ELSE '' END
      WHEN COALESCE(fl.fluor_code,'') <> '' THEN
        fl.fluor_code
      ELSE ''
    END AS fluor_token
  FROM tx_sources ts
  JOIN public.rnas               r   ON ts.kind_code = 'rna' AND r.rna_code = ts.treat_code
  JOIN public.join_rna_fusions   jrf ON jrf.rna_id = r.id
  JOIN public.fusions            f   ON f.id = jrf.fusion_id
  LEFT JOIN public.fluors        fl  ON fl.id = f.fluor_id
  LEFT JOIN public.tags          tg  ON tg.id = f.tag_id
  WHERE CASE
          WHEN COALESCE(fl.fluor_code,'') <> '' AND COALESCE(tg.tag_code,'') <> '' THEN
            fl.fluor_code || ':' || tg.tag_code ||
            CASE WHEN f.tag_pos IS NOT NULL AND f.tag_pos <> '' THEN '(' || f.tag_pos || ')' ELSE '' END
          WHEN COALESCE(fl.fluor_code,'') <> '' THEN
            fl.fluor_code
          ELSE ''
        END <> ''
),

tx_dye AS (
  SELECT DISTINCT
    ts.treated_clutch_code,
    COALESCE(d.dye_code,'') AS fluor_token
  FROM tx_sources ts
  JOIN public.dyes          d ON ts.kind_code = 'dye' AND d.dye_code = ts.treat_code
  WHERE COALESCE(d.dye_code,'') <> ''
),

tx_union AS (
  SELECT * FROM tx_plasmid
  UNION ALL
  SELECT * FROM tx_rna
  UNION ALL
  SELECT * FROM tx_dye
),

tx_tokens AS (
  SELECT
    treated_clutch_code,
    trim(fluor_token) AS token
  FROM tx_union
  WHERE trim(fluor_token) <> ''
),

tx_rollup AS (
  SELECT
    treated_clutch_code,
    string_agg(DISTINCT token, ' + ' ORDER BY token) AS treatment_fluors_rollup
  FROM tx_tokens
  GROUP BY treated_clutch_code
)

SELECT
  g.treated_clutch_code,
  g.group_created_at,
  g.clutch_instance_id,
  vc.clutch_code,
  vc.clutch_birthday,
  vc.cross_code,
  vc.cross_date,

  g.treatments_count_group,
  g.treatments_codes_group    AS treatment_codes_rollup,
  g.treatments_names_group    AS treatment_names_rollup,

  vc.mom_fish_code,
  vc.dad_fish_code,
  vc.mom_genotype,
  vc.dad_genotype,
  vc.mom_fusions,
  vc.dad_fusions,

  vc.clutch_genotype,
  vc.clutch_genotype_pretty,
  vc.genotype_codes_rollup,
  vc.allele_names_rollup,
  vc.genotype_fusions_rollup,
  COALESCE(tr.treatment_fluors_rollup, '') AS treatment_fluors_rollup,

  (COALESCE(tr.treatment_fluors_rollup, '') || '  >  ' ||
   COALESCE(vc.genotype_fusions_rollup, '')) AS treatment_vs_genotype_fusions,

  (COALESCE(g.treatments_codes_group, '') || '  >  ' ||
   COALESCE(vc.genotype_codes_rollup, '')) AS treatment_vs_genotype_codes,

  (COALESCE(g.treatments_names_group, '') || '  >  ' ||
   COALESCE(vc.allele_names_rollup, ''))   AS treatment_vs_allele_names

FROM grp g
LEFT JOIN vc       ON vc.clutch_instance_id = g.clutch_instance_id
LEFT JOIN tx_rollup tr ON tr.treated_clutch_code = g.treated_clutch_code
ORDER BY vc.clutch_code, g.group_created_at;

COMMIT;
