BEGIN;
CREATE OR REPLACE VIEW public.v_overview_mounts AS
SELECT
  m.mount_code,
  m.mounting_orientation,
  m.n_top,
  m.n_bottom,
  m.time_mounted AS mounted_at,
  ci.clutch_instance_code AS clutch_code,
  ci.created_at AS created_at,
  u.email AS operator,
  'Bruker 3D'::text AS instrument,
  ''::text AS notes
FROM public.mounts m
JOIN public.clutch_instances ci ON ci.id = m.clutch_instance_id
LEFT JOIN auth.users u ON u.id = ci.created_by
ORDER BY m.time_mounted DESC;
COMMIT;
