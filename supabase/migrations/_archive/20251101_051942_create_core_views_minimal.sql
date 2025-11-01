-- Minimal, shape-stable core views for a clean rebuild
-- Assumes base tables exist: fish, tanks, tank_pairs, crosses, clutches, clutch_instances,
-- plasmids, fluors, tags, fusions, plasmid_fusions, clutch_materials

-- v_fish: thin wrapper over fish with stable column names
CREATE OR REPLACE VIEW public.v_fish AS
SELECT
  f.fish_code::text  AS fish_code,
  f.created_at       AS created_at
FROM public.fish f;

-- v_tanks: thin wrapper over tanks with stable column names
CREATE OR REPLACE VIEW public.v_tanks AS
SELECT
  t.tank_code::text  AS tank_code,
  t.fish_code::text  AS fish_code,
  t.created_at       AS created_at
FROM public.tanks t;

-- v_clutch_treatments: rollup from generic link clutch_materials
CREATE OR REPLACE VIEW public.v_clutch_treatments AS
SELECT
  cm.clutch_instance_id                            AS clutch_instance_id,
  COUNT(*)::int                                    AS treatments_count_effective,
  string_agg(
    DISTINCT COALESCE(NULLIF(cm.material_name,''), cm.material_code),
    ' + ' ORDER BY COALESCE(NULLIF(cm.material_name,''), cm.material_code)
  )                                                AS treatments_pretty_effective,
  MAX(cm.created_at)                               AS last_treatment_at
FROM public.clutch_materials cm
GROUP BY cm.clutch_instance_id;

-- v_clutch_instances: append treatment rollups and a deterministic rollup field
CREATE OR REPLACE VIEW public.v_clutch_instances AS
SELECT
  ci.clutch_instance_code               AS clutch_code,
  ci.created_at::date                   AS clutch_birthday,
  ''::text                              AS cross_name_pretty,
  ''::text                              AS clutch_name,
  COALESCE(ci.clutch_genotype_pretty,'')          AS clutch_genotype_pretty,
  ''::text                              AS clutch_strain_pretty,
  COALESCE(vt.treatments_count_effective,0)::int  AS treatments_count_effective,
  COALESCE(vt.treatments_pretty_effective,'')     AS treatments_pretty_effective,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
      THEN vt.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
    ELSE COALESCE(vt.treatments_pretty_effective, ci.clutch_genotype_pretty, '')
  END                                             AS genotype_treatment_rollup_effective,
  ''::text                                        AS created_by_instance,
  ci.created_at                                   AS created_at_instance
FROM public.clutch_instances ci
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = ci.id;

-- v_crosses: thin wrapper over crosses (keep only universally-present fields)
CREATE OR REPLACE VIEW public.v_crosses AS
SELECT
  c.id,
  c.tank_pair_code,
  c.cross_run_code,
  c.cross_date,
  c.created_at
FROM public.crosses c;
