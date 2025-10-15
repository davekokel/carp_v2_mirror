CREATE OR REPLACE VIEW public.v_cross_concepts_overview AS
SELECT
  cp.clutch_code     AS conceptual_cross_code,
  cp.clutch_name     AS name,
  cp.clutch_nickname AS nickname,
  hum.mom_tank_label AS mom_code,
  hum.dad_tank_label AS dad_code,
  hum.mom_tank_label AS mom_code_tank,
  hum.dad_tank_label AS dad_code_tank,
  cp.created_at
FROM public.vw_clutches_concept_overview cp
LEFT JOIN public.vw_clutches_overview_human hum
  ON hum.clutch_code = cp.clutch_code;
