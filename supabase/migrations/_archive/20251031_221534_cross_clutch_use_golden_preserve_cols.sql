-- Rebuild v_cross_clutch_instances using the golden clutch view,
-- but preserve existing column names/order to satisfy CREATE OR REPLACE rules.

CREATE OR REPLACE VIEW public.v_cross_clutch_instances AS
SELECT
  ci.id                  AS cross_instance_id,
  ci.cross_run_code      AS cross_code,
  ci.cross_date          AS cross_date,
  ci.tank_pair_code      AS tank_pair_code,
  cl.id                  AS clutch_instance_id,       -- keep this position/name
  cl.clutch_instance_code AS clutch_code,             -- keep this position/name

  -- Pull canonical fields from the golden clutch view (joined by code)
  g.clutch_genotype_effective,
  g.treatments_count_effective,
  g.treatments_pretty_effective,
  g.treatments_genotype_effective,
  g.last_treatment_at

FROM public.cross_instances ci
LEFT JOIN public.clutch_instances cl
  ON cl.cross_instance_id = ci.id
LEFT JOIN public.v_clutch_instances g    -- golden view
  ON g.clutch_code = cl.clutch_instance_code

ORDER BY ci.cross_date DESC NULLS LAST, ci.cross_run_code;

COMMENT ON VIEW public.v_cross_clutch_instances IS
  'Cross + Clutch overview using golden v_clutch_instances (no recompute).';
