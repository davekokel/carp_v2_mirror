BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances AS
WITH tr AS (
  SELECT
    jct.clutch_instance_id,
    COUNT(*)::int AS treatments_count_effective,
    string_agg(
      DISTINCT NULLIF(btrim(COALESCE(jct.treatment_name, jct.treatment_code)), ''),
      ' + ' ORDER BY NULLIF(btrim(COALESCE(jct.treatment_name, jct.treatment_code)), '')
    ) AS treatments_pretty_effective
  FROM public.join_clutch_treatments jct
  GROUP BY jct.clutch_instance_id
),
base AS (
  SELECT
    ci.clutch_instance_code                  AS clutch_code,
    (cr.cross_date + INTERVAL '1 day')::date AS clutch_birthday,

    -- ✂️ remove "CR(… ) • " prefix → just mom × dad
    (COALESCE(vtp.mom_fish_code,'?') || ' × ' || COALESCE(vtp.dad_fish_code,'?'))
                                              AS cross_name_pretty,

    -- fill previously-blank fields from clutch_instances
    COALESCE(ci.clutch_name,'')               AS clutch_name,
    COALESCE(ci.clutch_genotype_pretty,'')    AS clutch_genotype_pretty,
    ''::text                                   AS clutch_strain_pretty,

    COALESCE(tr.treatments_count_effective,0) AS treatments_count_effective,
    COALESCE(tr.treatments_pretty_effective,'') AS treatments_pretty_effective,

    CASE
      WHEN COALESCE(tr.treatments_pretty_effective,'') <> '' AND COALESCE(ci.clutch_genotype_pretty,'') <> ''
        THEN tr.treatments_pretty_effective || ' > ' || ci.clutch_genotype_pretty
      WHEN COALESCE(tr.treatments_pretty_effective,'') <> ''
        THEN tr.treatments_pretty_effective
      ELSE COALESCE(ci.clutch_genotype_pretty,'')
    END                                        AS genotype_treatment_rollup_effective,

    COALESCE(cr.created_by,'')                 AS created_by_instance,
    COALESCE(cr.created_at, now())             AS created_at_instance

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
