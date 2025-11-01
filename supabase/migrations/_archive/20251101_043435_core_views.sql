SET search_path = public;

CREATE OR REPLACE VIEW public.v_fish AS
SELECT id, fish_code, created_at
FROM public.fish;

CREATE OR REPLACE VIEW public.v_tanks AS
SELECT id, tank_code, created_at
FROM public.tanks;

CREATE OR REPLACE VIEW public.v_clutch_treatments AS
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

CREATE OR REPLACE VIEW public.v_clutch_instances AS
SELECT
  ci.id                          AS clutch_instance_id,
  ci.clutch_instance_code        AS clutch_code,
  ci.cross_instance_id,
  ci.tank_pair_code,
  ci.clutch_genotype_pretty,
  COALESCE(vt.treatments_count_effective,0)::int            AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective,''::text)          AS treatments_pretty_effective,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
      THEN vt.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
    ELSE COALESCE(vt.treatments_pretty_effective, ci.clutch_genotype_pretty, ''::text)
  END                                                        AS treatments_genotype_effective,
  COALESCE(vt.last_treatment_at, ci.created_at)              AS last_treatment_at,
  ci.created_at
FROM public.clutch_instances ci
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = ci.id;

CREATE OR REPLACE VIEW public.v_crosses AS
SELECT
  id,
  tank_pair_code,
  cross_run_code,
  cross_date,
  run_nn,
  created_by,
  created_at
FROM public.crosses;
