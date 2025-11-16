BEGIN;

DROP VIEW IF EXISTS public.v_clutches_overview;

CREATE VIEW public.v_clutches_overview AS
WITH geno_labels AS (
  SELECT
    ceg.clutch_instance_id,
    string_agg(DISTINCT ceg.transgene_base_code, ' + ' ORDER BY ceg.transgene_base_code) AS genotype_codes_rollup,
    string_agg(DISTINCT ceg.allele_label,        ' + ' ORDER BY ceg.allele_label)        AS allele_names_rollup
  FROM public.clutch_expected_genotypes ceg
  GROUP BY ceg.clutch_instance_id
),
geno_tokens AS (
  SELECT
    ceg.clutch_instance_id,
    CASE
      WHEN fl.fluor_code IS NOT NULL AND tg.tag_code IS NOT NULL THEN
        fl.fluor_code || ':' || tg.tag_code ||
        CASE WHEN f.tag_pos IS NOT NULL AND f.tag_pos <> '' THEN '(' || f.tag_pos || ')' ELSE '' END
      WHEN fl.fluor_code IS NOT NULL THEN
        fl.fluor_code
      ELSE NULL
    END AS token
  FROM public.clutch_expected_genotypes ceg
  JOIN public.plasmids p              ON p.code = ceg.transgene_base_code
  JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
  JOIN public.fusions f               ON f.id = jpf.fusion_id
  LEFT JOIN public.fluors fl          ON fl.id = f.fluor_id
  LEFT JOIN public.tags   tg          ON tg.id = f.tag_id
),
geno_fusions AS (
  SELECT
    clutch_instance_id,
    string_agg(DISTINCT token, ' + ' ORDER BY token) AS genotype_fusions_rollup
  FROM geno_tokens
  WHERE token IS NOT NULL AND token <> ''
  GROUP BY clutch_instance_id
)
SELECT
  ci.id                    AS clutch_id,
  ci.clutch_instance_code  AS clutch_code,
  ci.created_at            AS clutch_created_at,
  ci.clutch_date           AS clutch_date,

  cr.id                    AS cross_id,
  cr.cross_run_code        AS cross_code,
  cr.created_at::date      AS cross_date,
  cr.created_at            AS cross_created_at,

  tp.id                    AS tank_pair_id,
  tp.tank_pair_code        AS tank_pair_code,

  mt.id                    AS mom_tank_id,
  mt.tank_code             AS mom_tank_code,
  mf.id                    AS mom_fish_id,
  mf.fish_code             AS mom_fish_code,
  mf.nickname              AS mom_nickname,
  mf.genetic_background    AS mom_genetic_background,
  mf.in_breeding_stage     AS mom_line_building_stage,
  mf.birthday              AS mom_birthday,

  dt.id                    AS dad_tank_id,
  dt.tank_code             AS dad_tank_code,
  df.id                    AS dad_fish_id,
  df.fish_code             AS dad_fish_code,
  df.nickname              AS dad_nickname,
  df.genetic_background    AS dad_genetic_background,
  df.in_breeding_stage     AS dad_line_building_stage,
  df.birthday              AS dad_birthday,

  mfo.genotype_pretty      AS mom_genotype,
  mfo.fusions              AS mom_fusions,
  dfo.genotype_pretty      AS dad_genotype,
  dfo.fusions              AS dad_fusions,

  ci.id                    AS clutch_instance_id,

  -- inline clutch genotype: allele labels
  COALESCE(gl.allele_names_rollup, '')     AS clutch_genotype,
  COALESCE(gl.allele_names_rollup, '')     AS clutch_genotype_pretty,

  -- new genotype rollups
  COALESCE(gl.genotype_codes_rollup,  '')  AS genotype_codes_rollup,
  COALESCE(gl.allele_names_rollup,   '')   AS allele_names_rollup,
  COALESCE(gf.genotype_fusions_rollup, '') AS genotype_fusions_rollup

FROM public.clutch_instances ci
JOIN public.crosses       cr  ON cr.id = ci.cross_instance_id
JOIN public.tank_pairs    tp  ON tp.id = cr.tank_pair_id
LEFT JOIN public.tanks    mt  ON mt.id = tp.mother_tank_id
LEFT JOIN public.fish     mf  ON mf.id = mt.fish_id
LEFT JOIN public.tanks    dt  ON dt.id = tp.father_tank_id
LEFT JOIN public.fish     df  ON df.id = dt.fish_id
LEFT JOIN public.v_fish_overview mfo ON mfo.fish_code_raw = mf.fish_code
LEFT JOIN public.v_fish_overview dfo ON dfo.fish_code_raw = df.fish_code
LEFT JOIN geno_labels  gl ON gl.clutch_instance_id = ci.id
LEFT JOIN geno_fusions gf ON gf.clutch_instance_id = ci.id;

COMMIT;
