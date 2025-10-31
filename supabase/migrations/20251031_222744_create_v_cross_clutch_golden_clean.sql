CREATE OR REPLACE VIEW public.v_cross_clutch AS
WITH base AS (
  SELECT
    ci.id                   AS cross_instance_id,
    ci.cross_run_code       AS cross_code,
    ci.cross_date           AS cross_date,
    ci.tank_pair_code       AS tank_pair_code,
    cl.id                   AS clutch_instance_id,
    cl.clutch_instance_code AS clutch_code,
    COALESCE(
      NULLIF(cl.observed_genotype_pretty,''),
      NULLIF(cl.expected_genotype_pretty,''),
      NULLIF(cl.clutch_genotype_pretty,'')
    )                       AS clutch_genotype_effective
  FROM public.cross_instances  ci
  LEFT JOIN public.clutch_instances cl
    ON cl.cross_instance_id = ci.id
)
SELECT
  b.*,
  COALESCE(vt.treatments_count_effective, 0)::int    AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective, ''::text) AS treatments_pretty_effective,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(b.clutch_genotype_effective,'') <> ''
      THEN vt.treatments_pretty_effective || ' > ' || b.clutch_genotype_effective
    ELSE COALESCE(vt.treatments_pretty_effective, b.clutch_genotype_effective, ''::text)
  END                                               AS treatments_genotype_effective,
  vt.last_treatment_at
FROM base b
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = b.clutch_instance_id
ORDER BY b.cross_date DESC NULLS LAST, b.cross_code;

COMMENT ON VIEW public.v_cross_clutch IS
  'Golden Cross+Clutch: joins v_clutch_treatments; coalesces clutch genotype (observed→expected→legacy).';
