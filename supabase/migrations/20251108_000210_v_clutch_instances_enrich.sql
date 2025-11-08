BEGIN;

DROP VIEW IF EXISTS public.v_clutch_instances;

CREATE VIEW public.v_clutch_instances AS
WITH tx AS (
  SELECT
    ci.clutch_instance_code                                                        AS clutch_code,
    COUNT(*)::int                                                                  AS treatments_count_effective,
    STRING_AGG(DISTINCT jct.treatment_code, ' + ' ORDER BY jct.treatment_code)     AS clutch_treatments_codes,
    STRING_AGG(
      DISTINCT COALESCE(NULLIF(jct.treatment_name,''), jct.treatment_code),
      ' + ' ORDER BY COALESCE(NULLIF(jct.treatment_name,''), jct.treatment_code)
    )                                                                              AS clutch_treatments_names
  FROM public.clutch_instances ci
  LEFT JOIN public.join_clutch_treatments jct
    ON jct.clutch_instance_id = ci.id
  GROUP BY ci.clutch_instance_code
)
SELECT
  -- picker fields
  ci.clutch_instance_code                                                             AS clutch_code,
  cr.cross_date::date                                                                  AS clutch_birthday,
  cr.cross_run_code                                                                    AS cross_name_pretty,
  ci.clutch_instance_code                                                              AS clutch_name,

  -- genotype: normalize any '×'/'x' to ';'
  REGEXP_REPLACE(COALESCE(ci.clutch_genotype_pretty,''), '\s*[×x]\s*', ' ; ', 'g')     AS clutch_genotype_pretty,

  ''::text                                                                             AS clutch_strain_pretty,

  -- treatments rollups
  COALESCE(tx.treatments_count_effective, 0)                                           AS treatments_count_effective,
  COALESCE(tx.clutch_treatments_names,  '')                                            AS treatments_pretty_effective,
  COALESCE(tx.clutch_treatments_codes,  '')                                            AS clutch_treatments_codes,
  COALESCE(tx.clutch_treatments_names,  '')                                            AS clutch_treatments_names,

  -- fusions placeholders (not computed here)
  ''::text                                                                             AS clutch_treatments_fusions,
  ''::text                                                                             AS clutch_genotype_fusions,
  ''::text                                                                             AS clutch_lineage_pretty,
  ''::text                                                                             AS clutch_lineage_fusions_pretty,
  ''::text                                                                             AS clutch_lineage_full_fusions_pretty,

  -- combined label: treatments > genotype (codes)
  CASE
    WHEN COALESCE(tx.clutch_treatments_codes,'') <> ''
      THEN tx.clutch_treatments_codes || ' > ' ||
           REGEXP_REPLACE(COALESCE(ci.clutch_genotype_pretty,''), '\s*[×x]\s*', ' ; ', 'g')
    ELSE REGEXP_REPLACE(COALESCE(ci.clutch_genotype_pretty,''), '\s*[×x]\s*', ' ; ', 'g')
  END                                                                                  AS treatment_genotype,

  -- provenance
  COALESCE(cr.created_by,'')                                                           AS created_by_instance,
  COALESCE(ci.created_at, cr.created_at)                                               AS created_at_instance

FROM public.clutch_instances  ci
JOIN public.crosses           cr  ON cr.id = ci.cross_instance_id
LEFT JOIN tx ON tx.clutch_code = ci.clutch_instance_code;

COMMIT;
