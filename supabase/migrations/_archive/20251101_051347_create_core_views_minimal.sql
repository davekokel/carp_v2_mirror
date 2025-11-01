-- Minimal, schema-safe core views. Only use columns we know exist in baseline tables.

-- v_fish: emit stable columns without assuming fish_name/nickname/background exist
CREATE OR REPLACE VIEW public.v_fish AS
SELECT
  f.fish_code::text              AS fish_code,
  ''::text                       AS fish_name,
  ''::text                       AS fish_nickname,
  ''::text                       AS genetic_background,
  COALESCE(f.created_at, now())  AS created_at
FROM public.fish f;

-- v_tanks: minimal view
CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.tank_code::text              AS tank_code,
  COALESCE(t.created_at, now())  AS created_at
FROM public.tanks t;

-- v_clutch_treatments: aggregate from clutch_materials (present in current tables)
CREATE OR REPLACE VIEW public.v_clutch_treatments AS
SELECT
  cm.clutch_instance_id,
  COUNT(*)::int AS treatments_count_effective,
  string_agg(
    DISTINCT COALESCE(NULLIF(trim(cm.material_name), ''), cm.material_code),
    ' + ' ORDER BY COALESCE(NULLIF(trim(cm.material_name), ''), cm.material_code)
  ) AS treatments_pretty_effective,
  MAX(cm.created_at) AS last_treatment_at
FROM public.clutch_materials cm
GROUP BY cm.clutch_instance_id;

-- v_clutch_instances: join baseline clutch_instances + rollups from v_clutch_treatments
CREATE OR REPLACE VIEW public.v_clutch_instances AS
SELECT
  ci.clutch_instance_code::text                           AS clutch_code,
  NULL::date                                              AS clutch_birthday,           -- not guaranteed in baseline
  ''::text                                                AS cross_name_pretty,         -- stub; pages can ignore
  ''::text                                                AS clutch_name,               -- stub
  COALESCE(ci.clutch_genotype_pretty, ''::text)           AS clutch_genotype_pretty,
  ''::text                                                AS clutch_strain_pretty,      -- stub
  COALESCE(vt.treatments_count_effective, 0)::int         AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective, ''::text)      AS treatments_pretty_effective,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
      THEN vt.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
    ELSE COALESCE(vt.treatments_pretty_effective, ci.clutch_genotype_pretty, ''::text)
  END                                                     AS genotype_treatment_rollup_effective,
  ''::text                                                AS created_by_instance,        -- stub
  COALESCE(ci.created_at, now())                          AS created_at_instance
FROM public.clutch_instances ci
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = ci.id;

-- v_crosses: minimal wrapper over crosses table
CREATE OR REPLACE VIEW public.v_crosses AS
SELECT
  c.id,
  c.tank_pair_code,
  c.cross_run_code,
  c.cross_date,
  COALESCE(c.created_at, now()) AS created_at
FROM public.crosses c;
