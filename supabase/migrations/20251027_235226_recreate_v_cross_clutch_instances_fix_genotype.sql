DROP VIEW IF EXISTS public.v_cross_clutch_instances;

CREATE VIEW public.v_cross_clutch_instances AS
SELECT
  x.id::uuid                    AS cross_instance_id,
  x.cross_run_code::text        AS cross_code,
  x.tank_pair_code::text        AS tank_pair_code,
  tp.fish_pair_code::text       AS fish_pair_code,
  tp.mom_fish_code::text        AS mom_fish_code,
  tp.dad_fish_code::text        AS dad_fish_code,
  tp.mother_tank_code::text     AS mom_tank_code,
  tp.father_tank_code::text     AS dad_tank_code,
  fm.genotype_rollup::text      AS mom_genotype,
  fd.genotype_rollup::text      AS dad_genotype,
  NULL::text                    AS clutch_genotype,
  (x.cross_date)::date          AS cross_date,
  x.created_at::timestamptz     AS cross_created_at,
  ci.id::uuid                   AS clutch_instance_id,
  ci.clutch_instance_code::text AS clutch_code,
  ci.created_at::timestamptz    AS clutch_created_at
FROM public.cross_instances x
LEFT JOIN public.v_tank_pairs tp   ON tp.tank_pair_code = x.tank_pair_code
LEFT JOIN public.v_fish_rich fm    ON fm.fish_code      = tp.mom_fish_code
LEFT JOIN public.v_fish_rich fd    ON fd.fish_code      = tp.dad_fish_code
LEFT JOIN public.clutch_instances ci ON ci.cross_instance_id = x.id;
