-- Drop dependents first to avoid rename/column-list conflicts during strict replays
DROP VIEW IF EXISTS public.cross_clutch_instances;
DROP VIEW IF EXISTS public.v_cross_clutch_instances;
DROP VIEW IF EXISTS public.v_tank_pairs;

-- Canonical v_tank_pairs: codes + ids only (no genotype columns here)
CREATE VIEW public.v_tank_pairs AS
SELECT
  tp.tank_pair_code::text AS tank_pair_code,
  fp.fish_pair_code::text AS fish_pair_code,
  fp.mom_fish_code::text  AS mom_fish_code,
  fp.dad_fish_code::text  AS dad_fish_code,
  tm.tank_code::text      AS mother_tank_code,
  tf.tank_code::text      AS father_tank_code
FROM public.tank_pairs tp
LEFT JOIN public.fish_pairs  fp ON fp.fish_pair_code = tp.fish_pair_code
LEFT JOIN public.tanks       tm ON tm.id = tp.mother_tank_id
LEFT JOIN public.tanks       tf ON tf.id = tp.father_tank_id;
