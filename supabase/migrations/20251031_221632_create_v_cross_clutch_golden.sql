-- New golden cross+clutch view that reuses public.v_clutch_instances (golden)
-- and exposes canonical names without conflicting with legacy view columns.

CREATE OR REPLACE VIEW public.v_cross_clutch AS
SELECT
  ci.id                    AS cross_instance_id,
  ci.cross_run_code        AS cross_code,
  ci.cross_date            AS cross_date,
  ci.tank_pair_code        AS tank_pair_code,

  cl.id                    AS clutch_instance_id,
  cl.clutch_instance_code  AS clutch_code,

  -- canonical fields reused from the golden clutch view
  g.clutch_genotype_effective,
  g.treatments_count_effective,
  g.treatments_pretty_effective,
  g.treatments_genotype_effective,
  g.last_treatment_at

FROM public.cross_instances ci
LEFT JOIN public.clutch_instances cl
  ON cl.cross_instance_id = ci.id
LEFT JOIN public.v_clutch_instances g   -- golden clutch view
  ON g.clutch_code = cl.clutch_instance_code

ORDER BY ci.cross_date DESC NULLS LAST, ci.cross_run_code;

COMMENT ON VIEW public.v_cross_clutch IS
  'Golden Cross+Clutch: reuses v_clutch_instances (golden rollups & genotype), clean canonical names.';
