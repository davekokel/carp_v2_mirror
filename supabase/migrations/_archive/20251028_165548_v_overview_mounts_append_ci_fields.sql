BEGIN;

DROP VIEW IF EXISTS public.v_overview_mounts;

-- Stable contract: includes CI fields as placeholders for now
CREATE VIEW public.v_overview_mounts AS
SELECT
  m.mount_code,
  m.time_mounted,
  m.mounting_orientation,
  m.clutch_instance_id,
  NULL::text        AS clutch_code,
  NULL::date        AS clutch_birthday,
  NULL::timestamptz AS created_at_instance
FROM public.mounts m
ORDER BY m.time_mounted DESC NULLS LAST;

COMMIT;
