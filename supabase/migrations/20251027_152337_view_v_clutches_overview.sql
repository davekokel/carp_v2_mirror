DROP VIEW IF EXISTS public.v_clutches_overview;

CREATE VIEW public.v_clutches_overview AS
WITH tcounts AS (
  SELECT
    vt.clutch_instance_id,
    COUNT(*)::int AS treatments_count,
    max(vt.last_treatment_at) AS last_treatment_at,
    string_agg(vt.treatments_pretty, '; ' ORDER BY vt.last_treatment_at DESC NULLS LAST) AS treatments_pretty
  FROM public.v_clutch_treatments vt
  GROUP BY vt.clutch_instance_id
)
SELECT
  vc.clutch_code,
  vc.clutch_name,
  vc.clutch_strain_pretty,
  vc.clutch_genotype_pretty,
  vc.cross_name_pretty,
  vc.genotype_treatment_rollup_effective,
  vc.treatments_count_effective,
  vc.treatments_pretty_effective,
  vc.created_at_instance,
  vc.created_by_instance,
  vc.clutch_birthday,
  COALESCE(tc.treatments_count, 0) AS treatments_count,
  tc.treatments_pretty,
  tc.last_treatment_at
FROM public.v_clutch_instances vc
LEFT JOIN public.v_clutch_treatments tc
  ON tc.clutch_instance_id::text = vc.clutch_code;
