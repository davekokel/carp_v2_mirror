DROP VIEW IF EXISTS public.v_cross_clutch_instances CASCADE;

CREATE VIEW public.v_cross_clutch_instances
(cross_instance_id, cross_code, tank_pair_code, fish_pair_code,
 mom_fish_code, dad_fish_code, mom_tank_code, dad_tank_code,
 mom_genotype, dad_genotype, clutch_genotype,
 cross_date, cross_created_at,
 clutch_instance_id, clutch_code, clutch_created_at)
AS
SELECT
  ci.id                           AS cross_instance_id,
  ci.cross_run_code               AS cross_code,
  ci.tank_pair_code               AS tank_pair_code,
  tp.fish_pair_code               AS fish_pair_code,
  tp.mom_fish_code                AS mom_fish_code,
  tp.dad_fish_code                AS dad_fish_code,
  tp.mother_tank_code             AS mom_tank_code,
  tp.father_tank_code             AS dad_tank_code,
  NULL::text                      AS mom_genotype,
  NULL::text                      AS dad_genotype,
  CASE
    WHEN COALESCE(NULL::text, '') <> '' AND COALESCE(NULL::text, '') <> ''
      THEN NULL::text || ' × ' || NULL::text
    ELSE COALESCE(NULL::text, NULL::text)
  END                             AS clutch_genotype,
  ci.cross_date                   AS cross_date,
  ci.created_at                   AS cross_created_at,
  cl.id                           AS clutch_instance_id,
  cl.clutch_instance_code         AS clutch_code,
  cl.created_at                   AS clutch_created_at
FROM public.cross_instances ci
LEFT JOIN public.clutch_instances cl
  ON cl.cross_instance_id = ci.id
LEFT JOIN public.v_tank_pairs tp
  ON tp.tank_pair_code = ci.tank_pair_code
ORDER BY ci.created_at DESC NULLS LAST, ci.cross_date DESC NULLS LAST;