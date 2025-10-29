BEGIN;

DROP VIEW IF EXISTS public.v_overview_mounts;

CREATE VIEW public.v_overview_mounts AS
SELECT
  -- stable mount columns
  m.mount_code,
  m.mounting_orientation,
  m.n_top,
  m.n_bottom,
  m.time_mounted                 AS mounted_at,
  ci.clutch_instance_code        AS clutch_code,
  ci.created_at                  AS created_at,
  COALESCE(x.created_by, '')     AS operator,
  'Bruker 3D'::text              AS instrument,
  m.notes                        AS notes,
  -- new clutch-linked fields
  vci.clutch_birthday,
  vci.genotype_treatment_rollup_effective,
  vci.treatments_count_effective AS treatment_count,
  tc.treatments_codes
FROM public.mounts m
JOIN public.clutch_instances ci
  ON ci.id = m.clutch_instance_id
LEFT JOIN public.cross_instances x
  ON x.id = ci.cross_instance_id
LEFT JOIN public.v_clutch_instances_display vci
  ON vci.clutch_code = ci.clutch_instance_code
LEFT JOIN LATERAL (
  SELECT string_agg(DISTINCT cit.material_code, ' + ' ORDER BY cit.material_code) AS treatments_codes
  FROM public.clutch_instance_treatments cit
  WHERE cit.clutch_instance_id = ci.id
) tc ON TRUE
ORDER BY m.time_mounted DESC;

COMMIT;
