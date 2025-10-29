BEGIN;

DROP VIEW IF EXISTS public.v_overview_mounts;

-- Canonical column order for now; we can enrich later once upstream columns stabilize
CREATE VIEW public.v_overview_mounts AS
SELECT
  m.mount_code,
  m.time_mounted,
  m.mounting_orientation,
  m.clutch_instance_id
FROM public.mounts m
ORDER BY m.time_mounted DESC NULLS LAST;

COMMIT;
