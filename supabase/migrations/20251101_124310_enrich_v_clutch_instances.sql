BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances AS
WITH cm AS (
  -- Prefer material_name from v_materials; fall back to stored name/code
  SELECT
    c.clutch_instance_id,
    COALESCE(vm.material_name, c.material_name, c.material_code) AS pretty_name
  FROM public.clutch_materials c
  LEFT JOIN public.v_materials vm
    ON lower(vm.material_type) = lower(c.material_type)
   AND lower(vm.material_code) = lower(c.material_code)
),
cm_roll AS (
  SELECT
    clutch_instance_id,
    COUNT(*)::int AS treatments_count_effective,
    string_agg(
      DISTINCT NULLIF(btrim(pretty_name), ''),
      ' + ' ORDER BY NULLIF(btrim(pretty_name), '')
    ) AS treatments_pretty_effective
  FROM cm
  GROUP BY clutch_instance_id
),
base AS (
  SELECT
    ci.id                                   AS clutch_instance_id,
    ci.clutch_instance_code                 AS clutch_code,
    cr.id                                   AS cross_id,
    cr.cross_run_code                       AS cross_run_code,
    cr.tank_pair_code                       AS tank_pair_code,

    -- birthday used by UI (petri DOB)
    (cr.cross_date + INTERVAL '1 day')::date AS clutch_birthday,

    -- Pretty cross name (graceful fallback)
    COALESCE(
      'CR(' || cr.cross_run_code || ') • ' ||
      COALESCE(vtp.mom_fish_code,'?') || ' × ' || COALESCE(vtp.dad_fish_code,'?'),
      'CR • ' || COALESCE(cr.tank_pair_code,'?')
    ) AS cross_name_pretty,

    -- Placeholders if not modeled
    ''::text                                AS clutch_name,
    COALESCE(ci.clutch_genotype_pretty,'')  AS clutch_genotype_pretty,
    ''::text                                AS clutch_strain_pretty,

    -- Treatments rollups
    COALESCE(r.treatments_count_effective,0)::int AS treatments_count_effective,
    COALESCE(r.treatments_pretty_effective,'')     AS treatments_pretty_effective,

    -- Treatments first, then genotype (UI recomputes if blank)
    CASE
      WHEN COALESCE(r.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
        THEN r.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
      WHEN COALESCE(r.treatments_pretty_effective,'') <> ''
        THEN r.treatments_pretty_effective
      ELSE COALESCE(ci.clutch_genotype_pretty,'')
    END AS genotype_treatment_rollup_effective,

    -- Instance audit
    COALESCE(ci.created_by, cr.created_by, '')    AS created_by_instance,
    COALESCE(ci.created_at, cr.created_at, now()) AS created_at_instance
  FROM public.clutch_instances ci
  LEFT JOIN public.crosses       cr  ON cr.id = ci.cross_instance_id
  LEFT JOIN public.v_tank_pairs  vtp ON vtp.tank_pair_code = cr.tank_pair_code
  LEFT JOIN cm_roll              r   ON r.clutch_instance_id = ci.id
)
SELECT
  clutch_code,
  clutch_birthday,
  cross_name_pretty,
  clutch_name,
  clutch_genotype_pretty,
  clutch_strain_pretty,
  treatments_count_effective,
  treatments_pretty_effective,
  genotype_treatment_rollup_effective,
  created_by_instance,
  created_at_instance
FROM base
ORDER BY created_at_instance DESC NULLS LAST, clutch_code;

COMMIT;
