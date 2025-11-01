-- Minimal, schema-true views – no references to non-existent columns.

-- 1) Rollup treatments from clutch_materials
DROP VIEW IF EXISTS public.v_clutch_treatments;
CREATE OR REPLACE VIEW public.v_clutch_treatments AS
SELECT
  cm.clutch_instance_id,
  COUNT(*)::int AS treatments_count_effective,
  string_agg(
    DISTINCT COALESCE(NULLIF(btrim(cm.material_name),''), cm.material_code),
    ' + ' ORDER BY COALESCE(NULLIF(btrim(cm.material_name),''), cm.material_code)
  ) AS treatments_pretty_effective,
  MAX(cm.created_at) AS last_treatment_at
FROM public.clutch_materials cm
GROUP BY cm.clutch_instance_id;

COMMENT ON VIEW public.v_clutch_treatments IS
'Rolls up clutch_materials to (count, pretty, last_treatment_at).';

-- 2) Clutch instances + resolved treatment rollups
DROP VIEW IF EXISTS public.v_clutch_instances;
CREATE OR REPLACE VIEW public.v_clutch_instances AS
SELECT
  ci.clutch_instance_code                  AS clutch_code,
  ci.created_at                            AS created_at_instance,
  COALESCE(vt.treatments_count_effective, 0)::int                 AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective, ''::text)              AS treatments_pretty_effective,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> ''
     AND COALESCE(ci.clutch_genotype_pretty,'')   <> ''
    THEN vt.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
    ELSE COALESCE(vt.treatments_pretty_effective, ci.clutch_genotype_pretty, ''::text)
  END                                                             AS genotype_treatment_rollup_effective,
  vt.last_treatment_at
FROM public.clutch_instances ci
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = ci.id;

COMMENT ON VIEW public.v_clutch_instances IS
'Clutch instances (code/created_at) with treatment rollups and simple rollup>genotype string.';

-- 3) Crosses wrapper (only universally present columns)
DROP VIEW IF EXISTS public.v_crosses;
CREATE OR REPLACE VIEW public.v_crosses AS
SELECT
  c.id,
  c.tank_pair_code,
  c.cross_run_code,
  c.cross_date,
  c.created_at
FROM public.crosses c;

COMMENT ON VIEW public.v_crosses IS
'Minimal crosses view: id, tank_pair_code, cross_run_code, cross_date, created_at.';
