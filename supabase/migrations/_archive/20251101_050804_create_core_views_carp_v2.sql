-- Core views bound to the canonical tables:
--   crosses, clutches, treatments, tanks, fish
-- Idempotent: all are CREATE OR REPLACE VIEW.

SET client_min_messages TO warning;

-- v_clutch_treatments: aggregate per clutch
CREATE OR REPLACE VIEW public.v_clutch_treatments AS
SELECT
  t.clutch_instance_id                         AS clutch_id,
  COUNT(*)::int                                AS treatments_count_effective,
  STRING_AGG(
    DISTINCT COALESCE(NULLIF(TRIM(t.material_name),''), t.material_code),
    ' + ' ORDER BY COALESCE(NULLIF(TRIM(t.material_name),''), t.material_code)
  )                                            AS treatments_pretty_effective,
  MAX(t.created_at)                            AS last_treatment_at
FROM public.treatments t
GROUP BY t.clutch_instance_id;

COMMENT ON VIEW public.v_clutch_treatments IS
  'Per-clutch rollup: count/pretty/last_treatment_at derived from public.treatments.';

-- v_clutch_instances: page-friendly clutch snapshot with rollups
-- (keeps legacy column names many pages expect)
CREATE OR REPLACE VIEW public.v_clutch_instances AS
SELECT
  cl.id::uuid                                  AS clutch_id,
  cl.clutch_instance_code                      AS clutch_code,
  cl.cross_instance_id                         AS cross_instance_id,
  cl.tank_pair_code                            AS tank_pair_code,
  COALESCE(cl.clutch_genotype_pretty,'')       AS clutch_genotype_pretty,
  COALESCE(vt.treatments_count_effective,0)::int          AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective,'')             AS treatments_pretty_effective,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(cl.clutch_genotype_pretty,'') <> ''
      THEN vt.treatments_pretty_effective || ' > ' || cl.clutch_genotype_pretty
    ELSE COALESCE(vt.treatments_pretty_effective, cl.clutch_genotype_pretty, ''::text)
  END                                                     AS genotype_treatment_rollup_effective,
  ''::text                                                AS created_by_instance,   -- compat
  cl.created_at                                           AS created_at_instance
FROM public.clutches cl
LEFT JOIN public.v_clutch_treatments vt
       ON vt.clutch_id = cl.id;

COMMENT ON VIEW public.v_clutch_instances IS
  'Clutch snapshot + treatment rollups (count/pretty/rollup).';

-- v_crosses: lightweight wrapper (stable columns)
CREATE OR REPLACE VIEW public.v_crosses AS
SELECT
  c.id,
  c.tank_pair_code,
  c.cross_run_code,
  c.cross_date,
  c.created_at,
  COALESCE(c.created_by,'') AS created_by
FROM public.crosses c;

COMMENT ON VIEW public.v_crosses IS
  'Stable wrapper for crosses table (run code/date + audit).';
