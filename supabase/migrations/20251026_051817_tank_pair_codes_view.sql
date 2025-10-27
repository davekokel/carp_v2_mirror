-- Bootstrap: drop dependents then create minimal v_tank_pairs
DROP VIEW IF EXISTS public.cross_clutch_instances;
DROP VIEW IF EXISTS public.v_cross_clutch_instances;
DROP VIEW IF EXISTS public.v_tank_pairs;

CREATE VIEW public.v_tank_pairs AS
SELECT
  tp.tank_pair_code::text AS tank_pair_code,
  fp.fish_pair_code::text AS fish_pair_code,
  fp.mom_fish_code::text  AS mom_fish_code,
  fp.dad_fish_code::text  AS dad_fish_code,
  NULL::text              AS mother_tank_code,
  NULL::text              AS father_tank_code
FROM public.tank_pairs tp
LEFT JOIN public.fish_pairs fp ON fp.fish_pair_code = tp.fish_pair_code;
