BEGIN;

-- Rebuild the canonical view used by the page
DROP VIEW IF EXISTS public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances AS
WITH tr AS (
  -- Roll up treatments attached to each clutch instance from the existing table
  SELECT
    t.clutch_instance_id,
    COUNT(*)::int AS treatments_count_effective,
    string_agg(
      DISTINCT NULLIF(btrim(COALESCE(t.material_name, t.material_code)), ''),
      ' + ' ORDER BY NULLIF(btrim(COALESCE(t.material_name, t.material_code)), '')
    ) AS treatments_pretty_effective,
    MAX(t.created_at) AS last_treatment_at
  FROM public.treatments t
  WHERE t.clutch_instance_id IS NOT NULL
  GROUP BY t.clutch_instance_id
),
base AS (
  SELECT
    ci.clutch_instance_code                  AS clutch_code,
    (cr.cross_date + INTERVAL '1 day')::date AS clutch_birthday,
    COALESCE(
      'CR(' || cr.cross_run_code || ') • ' ||
      COALESCE(vtp.mom_fish_code,'?') || ' × ' || COALESCE(vtp.dad_fish_code,'?'),
      'CR • ' || COALESCE(cr.tank_pair_code,'?')
    )                                        AS cross_name_pretty,
    ''::text                                  AS clutch_name,
    COALESCE(ci.clutch_genotype_pretty,'')    AS clutch_genotype_pretty,
    ''::text                                  AS clutch_strain_pretty,
    COALESCE(tr.treatments_count_effective,0)::int        AS treatments_count_effective,
    COALESCE(tr.treatments_pretty_effective,'')            AS treatments_pretty_effective,
    CASE
      WHEN COALESCE(tr.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
        THEN tr.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
      WHEN COALESCE(tr.treatments_pretty_effective,'') <> ''
        THEN tr.treatments_pretty_effective
      ELSE COALESCE(ci.clutch_genotype_pretty,'')
    END                                                    AS genotype_treatment_rollup_effective,
    COALESCE(ci.created_by,  cr.created_by,  '')           AS created_by_instance,
    COALESCE(ci.created_at,  cr.created_at,  now())        AS created_at_instance
  FROM public.clutch_instances ci
  LEFT JOIN public.crosses       cr  ON cr.id = ci.cross_instance_id
  LEFT JOIN public.v_tank_pairs  vtp ON vtp.tank_pair_code = cr.tank_pair_code
  LEFT JOIN tr                        ON tr.clutch_instance_id = ci.id
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
