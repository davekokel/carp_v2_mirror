BEGIN;

CREATE OR REPLACE VIEW public.v_overview_mounts AS
SELECT
  -- existing columns first (stable order)
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
  -- appended clutch_instance fields (safe additions)
  ci.clutch_instance_code        AS clutch_instance_code,
  ci.label                       AS ci_label,
  ci.red_intensity               AS ci_red_intensity,
  ci.green_intensity             AS ci_green_intensity,
  ci.notes                       AS ci_notes,
  ci.red_selected                AS ci_red_selected,
  ci.green_selected              AS ci_green_selected,
  ci.annotated_by                AS ci_annotated_by,
  ci.annotated_at                AS ci_annotated_at
FROM public.mounts m
JOIN public.clutch_instances ci
  ON ci.id = m.clutch_instance_id
LEFT JOIN public.cross_instances x
  ON x.id = ci.cross_instance_id
ORDER BY m.time_mounted DESC;

COMMIT;
