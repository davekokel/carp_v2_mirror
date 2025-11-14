BEGIN;

DROP VIEW IF EXISTS public.v_clutches_overview;

CREATE VIEW public.v_clutches_overview AS
WITH genos AS (
  SELECT
    ceg.clutch_instance_id,
    string_agg(
      DISTINCT COALESCE(
        ceg.allele_label,
        ceg.transgene_base_code || '(' || ceg.allele_number::text || ')'
      ),
      ' / ' ORDER BY COALESCE(
        ceg.allele_label,
        ceg.transgene_base_code || '(' || ceg.allele_number::text || ')'
      )
    ) AS clutch_genotype,
    string_agg(
      DISTINCT COALESCE(
        ceg.allele_label,
        ceg.transgene_base_code || '(' || ceg.allele_number::text || ')'
      ),
      ', ' ORDER BY COALESCE(
        ceg.allele_label,
        ceg.transgene_base_code || '(' || ceg.allele_number::text || ')'
      )
    ) AS clutch_genotype_pretty
  FROM public.clutch_expected_genotypes ceg
  GROUP BY ceg.clutch_instance_id
)
SELECT
  -- 1–4: clutch basics
  ci.id                   AS clutch_id,
  ci.clutch_instance_code AS clutch_code,
  ci.created_at           AS clutch_created_at,
  ci.clutch_date          AS clutch_date,

  -- 5–8: cross
  cr.id                   AS cross_id,
  cr.cross_run_code       AS cross_code,
  cr.created_at::date     AS cross_date,
  cr.created_at           AS cross_created_at,

  -- 9–10: tank pair
  tp.id                   AS tank_pair_id,
  tp.tank_pair_code       AS tank_pair_code,

  -- 11–18: mother tank + fish
  mt.id                   AS mom_tank_id,
  mt.tank_code            AS mom_tank_code,
  mf.id                   AS mom_fish_id,
  mf.fish_code            AS mom_fish_code,
  mf.nickname             AS mom_nickname,
  mf.genetic_background   AS mom_genetic_background,
  mf.in_breeding_stage    AS mom_line_building_stage,
  mf.birthday             AS mom_birthday,

  -- 19–26: father tank + fish
  dt.id                   AS dad_tank_id,
  dt.tank_code            AS dad_tank_code,
  df.id                   AS dad_fish_id,
  df.fish_code            AS dad_fish_code,
  df.nickname             AS dad_nickname,
  df.genetic_background   AS dad_genetic_background,
  df.in_breeding_stage    AS dad_line_building_stage,
  df.birthday             AS dad_birthday,

  -- 27–30: parent rollups from v_fish_overview
  mfo.genotype_pretty     AS mom_genotype,
  mfo.fusions             AS mom_fusions,
  dfo.genotype_pretty     AS dad_genotype,
  dfo.fusions             AS dad_fusions,

  -- 31: clutch_instance_id
  ci.id                   AS clutch_instance_id,

  -- 32–33: genotype rollup from clutch_expected_genotypes
  COALESCE(genos.clutch_genotype, '')        AS clutch_genotype,
  COALESCE(genos.clutch_genotype_pretty, '') AS clutch_genotype_pretty

FROM public.clutch_instances ci
JOIN public.crosses       cr  ON cr.id = ci.cross_instance_id
JOIN public.tank_pairs    tp  ON tp.id = cr.tank_pair_id
LEFT JOIN public.tanks    mt  ON mt.id = tp.mother_tank_id
LEFT JOIN public.fish     mf  ON mf.id = mt.fish_id
LEFT JOIN public.tanks    dt  ON dt.id = tp.father_tank_id
LEFT JOIN public.fish     df  ON df.id = dt.fish_id
LEFT JOIN public.v_fish_overview mfo ON mfo.fish_code_raw = mf.fish_code
LEFT JOIN public.v_fish_overview dfo ON dfo.fish_code_raw = df.fish_code
LEFT JOIN genos ON genos.clutch_instance_id = ci.id;

COMMIT;
