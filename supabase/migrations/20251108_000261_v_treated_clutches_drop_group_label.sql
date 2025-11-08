BEGIN;

DROP VIEW IF EXISTS public.v_treated_clutches;

CREATE VIEW public.v_treated_clutches AS
WITH tx AS (
  SELECT
    jct.treated_clutch_id,
    COUNT(*)::int AS treatments_count,
    STRING_AGG(DISTINCT jct.treatment_code, ' + ' ORDER BY jct.treatment_code) AS treatments_codes,
    STRING_AGG(
      DISTINCT COALESCE(NULLIF(jct.treatment_name,''), jct.treatment_code),
      ' + ' ORDER BY COALESCE(NULLIF(jct.treatment_name,''), jct.treatment_code)
    ) AS treatments_names
  FROM public.join_clutch_treatments jct
  GROUP BY jct.treated_clutch_id
)
SELECT
  tc.treated_clutch_code,
  tc.id::uuid                               AS treated_clutch_id,
  tc.created_at                             AS group_created_at,
  ci.clutch_instance_code                   AS clutch_code,
  cr.cross_run_code                         AS cross_name_pretty,
  cr.cross_date::date                       AS clutch_birthday,
  REGEXP_REPLACE(COALESCE(ci.clutch_genotype_pretty,''), '\s*[×x]\s*', ' ; ', 'g') AS clutch_genotype_pretty,
  COALESCE(tx.treatments_count, 0)          AS treatments_count_group,
  COALESCE(tx.treatments_codes,  '')        AS treatments_codes_group,
  COALESCE(tx.treatments_names,  '')        AS treatments_names_group,
  CASE
    WHEN COALESCE(tx.treatments_codes,'') <> ''
      THEN tx.treatments_codes || ' > ' ||
           REGEXP_REPLACE(COALESCE(ci.clutch_genotype_pretty,''), '\s*[×x]\s*', ' ; ', 'g')
    ELSE REGEXP_REPLACE(COALESCE(ci.clutch_genotype_pretty,''), '\s*[×x]\s*', ' ; ', 'g')
  END                                        AS treatment_genotype_group
FROM public.treated_clutches tc
JOIN public.clutch_instances  ci ON ci.id = tc.clutch_instance_id
JOIN public.crosses           cr ON cr.id = ci.cross_instance_id
LEFT JOIN tx ON tx.treated_clutch_id = tc.id;

COMMIT;
