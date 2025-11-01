-- core, stable views — no deps on any trash_* objects

CREATE OR REPLACE VIEW public.v_fish AS
SELECT
  f.id::uuid                 AS fish_uuid,
  f.fish_code::text          AS fish_code,
  COALESCE(f.fish_name,'')   AS fish_name,
  COALESCE(f.fish_nickname,'') AS fish_nickname,
  COALESCE(f.genetic_background,'') AS genetic_background,
  f.created_at
FROM public.fish f;

CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.id::uuid                 AS tank_uuid,
  t.tank_code::text          AS tank_code,
  COALESCE(t.status,'')      AS status,
  t.created_at
FROM public.tanks t;

-- roll up clutch materials into count/pretty + last_treatment_at
CREATE OR REPLACE VIEW public.v_clutch_treatments AS
SELECT
  cm.clutch_instance_id::uuid                      AS clutch_instance_id,
  COUNT(*)::int                                    AS treatments_count_effective,
  string_agg(DISTINCT COALESCE(cm.material_name, cm.material_code),
             ' + ' ORDER BY COALESCE(cm.material_name, cm.material_code)) AS treatments_pretty_effective,
  MAX(cm.created_at)                                AS last_treatment_at
FROM public.clutch_materials cm
GROUP BY cm.clutch_instance_id;

-- golden clutch instances (keeps expected column names)
CREATE OR REPLACE VIEW public.v_clutch_instances AS
SELECT
  ci.clutch_instance_code           AS clutch_code,
  (ci.created_at)::date             AS clutch_birthday,
  ''::text                          AS cross_name_pretty,
  ''::text                          AS clutch_name,
  COALESCE(ci.clutch_genotype_pretty,'') AS clutch_genotype_pretty,
  ''::text                          AS clutch_strain_pretty,
  COALESCE(vt.treatments_count_effective,0)::int    AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective,'')       AS treatments_pretty_effective,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
      THEN vt.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
    ELSE COALESCE(vt.treatments_pretty_effective, ci.clutch_genotype_pretty, ''::text)
  END                                              AS genotype_treatment_rollup_effective,
  COALESCE(ci.created_by,'')                       AS created_by_instance,
  ci.created_at                                    AS created_at_instance
FROM public.clutch_instances ci
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = ci.id;

-- crosses view (lightweight wrapper over table)
CREATE OR REPLACE VIEW public.v_crosses AS
SELECT
  c.id,
  c.tank_pair_code,
  c.cross_run_code,
  c.cross_date,
  c.run_nn,
  COALESCE(c.created_by,'') AS created_by,
  c.created_at
FROM public.cross_instances c;
