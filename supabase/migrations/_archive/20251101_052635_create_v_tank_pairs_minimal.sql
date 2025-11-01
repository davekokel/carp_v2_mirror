-- Minimal tank-pairs view (no fancy genotype; just codes + timestamps)
CREATE OR REPLACE VIEW public.v_tank_pairs AS
SELECT
  tp.tank_pair_code,
  vtm.fish_code  AS mom_fish_code,
  vtm.tank_code  AS mom_tank_code,
  vtf.fish_code  AS dad_fish_code,
  vtf.tank_code  AS dad_tank_code,
  tp.created_at
FROM public.tank_pairs tp
LEFT JOIN public.v_tanks vtm ON vtm.tank_uuid = tp.mother_tank_id
LEFT JOIN public.v_tanks vtf ON vtf.tank_uuid = tp.father_tank_id;
