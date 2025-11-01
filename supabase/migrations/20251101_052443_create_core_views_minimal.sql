-- Minimal, baseline-safe core views
-- Assumptions:
--   tanks.tank_code, tanks.created_at
--   clutch_instances.(id, clutch_instance_code, clutch_genotype_pretty, created_at)
--   clutch_materials.(clutch_instance_id, material_type/code/name, created_at)
--   crosses.(id, tank_pair_code, cross_run_code, cross_date, created_at)

-- 1) v_tanks: minimal shape
DROP VIEW IF EXISTS public.v_tanks CASCADE;
CREATE VIEW public.v_tanks AS
SELECT
  COALESCE(t.tank_code,'')::text AS tank_code,
  COALESCE(t.created_at, now())  AS created_at
FROM public.tanks t;
COMMENT ON VIEW public.v_tanks IS 'Minimal tanks view: tank_code, created_at.';

-- 2) v_clutch_treatments: rollups from clutch_materials (canonical *_effective names)
DROP VIEW IF EXISTS public.v_clutch_treatments CASCADE;
CREATE VIEW public.v_clutch_treatments AS
SELECT
  cm.clutch_instance_id,
  COUNT(*)::int AS treatments_count_effective,
  string_agg(
    DISTINCT COALESCE(cm.material_name, cm.material_code),
    ' + ' ORDER BY COALESCE(cm.material_name, cm.material_code)
  ) AS treatments_pretty_effective,
  MAX(cm.created_at) AS last_treatment_at
FROM public.clutch_materials cm
GROUP BY cm.clutch_instance_id;
COMMENT ON VIEW public.v_clutch_treatments IS
'Rollups per clutch_instance from clutch_materials: count/pretty/last_treatment_at.';

-- 3) v_clutch_instances: minimal plus treatment rollups and simple > join
DROP VIEW IF EXISTS public.v_clutch_instances CASCADE;
CREATE VIEW public.v_clutch_instances AS
SELECT
  COALESCE(ci.clutch_instance_code,'')::text        AS clutch_code,
  ci.created_at                                     AS created_at_instance,
  COALESCE(ci.clutch_genotype_pretty,'')::text      AS clutch_genotype_pretty,
  COALESCE(vt.treatments_count_effective, 0)::int   AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective, ''::text) AS treatments_pretty_effective,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
      THEN vt.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
    ELSE COALESCE(vt.treatments_pretty_effective, ci.clutch_genotype_pretty, ''::text)
  END                                               AS genotype_treatment_rollup_effective,
  COALESCE(vt.last_treatment_at, ci.created_at)     AS last_treatment_at
FROM public.clutch_instances ci
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = ci.id;
COMMENT ON VIEW public.v_clutch_instances IS
'Minimal clutch instances + treatment rollups with a simple "treatments > genotype" field.';

-- 4) v_crosses: thin wrapper on crosses
DROP VIEW IF EXISTS public.v_crosses CASCADE;
CREATE VIEW public.v_crosses AS
SELECT
  c.id,
  c.tank_pair_code,
  c.cross_run_code,
  c.cross_date,
  c.created_at
FROM public.crosses c;
COMMENT ON VIEW public.v_crosses IS 'Thin wrapper over crosses with universally present fields.';
