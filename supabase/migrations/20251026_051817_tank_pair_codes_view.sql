-- Bootstrap: drop dependents, create minimal v_tank_pairs (later files overwrite)
DROP VIEW IF EXISTS public.cross_clutch_instances;
DROP VIEW IF EXISTS public.v_overview_mounts, public.v_clutch_instances_display, public.v_clutch_instances, public.v_clutches_for_entry, public.v_cross_clutch_instances CASCADE;
DROP VIEW IF EXISTS public.v_tank_pairs;

CREATE VIEW public.v_tank_pairs AS
SELECT
  tp.tank_pair_code::text AS tank_pair_code,
  NULL::text              AS fish_pair_code,
  NULL::text              AS mom_fish_code,
  NULL::text              AS dad_fish_code,
  NULL::text              AS mother_tank_code,
  NULL::text              AS father_tank_code
FROM public.tank_pairs tp;
