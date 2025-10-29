BEGIN;

DROP VIEW IF EXISTS public.v_overview_mounts;

CREATE VIEW public.v_overview_mounts AS
SELECT
  m.mount_code,
  m.time_mounted,
  m.mounting_orientation,
  m.clutch_instance_id,
  NULL::int            AS treatments_count_effective,
  NULL::text           AS treatments_pretty_effective,
  NULL::text           AS genotype_treatment_rollup_effective,
  NULL::text           AS parent_genotype_pretty
FROM public.mounts m
ORDER BY m.time_mounted DESC NULLS LAST;

COMMIT;
