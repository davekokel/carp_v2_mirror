-- Cross + Clutch should read the golden clutch view (no recompute)
CREATE OR REPLACE VIEW public.v_cross_clutch_instances AS
SELECT
  ci.id               AS cross_instance_id,
  ci.cross_run_code   AS cross_code,
  ci.cross_date,
  ci.tank_pair_code,
  cl.clutch_instance_code AS clutch_code,
  g.clutch_genotype_effective,
  g.treatments_count_effective,
  g.treatments_pretty_effective,
  g.treatments_genotype_effective,
  g.last_treatment_at
FROM public.cross_instances ci
LEFT JOIN public.clutch_instances cl
  ON cl.cross_instance_id = ci.id
LEFT JOIN public.v_clutch_instances g      -- golden
  ON g.clutch_code = cl.clutch_instance_code
ORDER BY ci.cross_date DESC NULLS LAST, ci.cross_run_code;
