DROP VIEW IF EXISTS public.v_tank_pairs CASCADE;

CREATE VIEW public.v_tank_pairs AS
SELECT
  tp.tank_pair_code,
  tm.tank_code AS mom_tank_code,
  tf.tank_code AS dad_tank_code,
  tp.created_at
FROM public.tank_pairs tp
LEFT JOIN public.tanks tm ON tm.id = tp.mother_tank_id
LEFT JOIN public.tanks tf ON tf.id = tp.father_tank_id;

COMMENT ON VIEW public.v_tank_pairs IS
'Minimal tank pairs view (joins base tanks by id): mom_tank_code, dad_tank_code, created_at.';
