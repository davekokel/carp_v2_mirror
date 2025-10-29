BEGIN;

DROP VIEW IF EXISTS public.v_overview_mounts;
DROP VIEW IF EXISTS public.v_clutch_instances_display;

CREATE VIEW public.v_clutch_instances_display
(clutch_code, clutch_birthday, cross_name_pretty, clutch_name,
 clutch_genotype_pretty, clutch_strain_pretty, treatments_count_effective,
 treatments_pretty_effective, genotype_treatment_rollup_effective,
 created_by_instance, created_at_instance,
 clutch_label, genotype_label, parent_genotype_pretty) AS
SELECT
  vci.clutch_code,
  vci.clutch_birthday,
  COALESCE(vci.cross_name_pretty, '')                AS cross_name_pretty,
  COALESCE(vci.clutch_name, '')                      AS clutch_name,
  COALESCE(vci.clutch_genotype_pretty, '')           AS clutch_genotype_pretty,
  COALESCE(vci.clutch_strain_pretty, '')             AS clutch_strain_pretty,
  COALESCE(vci.treatments_count_effective, 0)::int   AS treatments_count_effective,
  COALESCE(vci.treatments_pretty_effective, '')      AS treatments_pretty_effective,
  COALESCE(
    vci.genotype_treatment_rollup_effective,
    NULLIF(vci.clutch_genotype_pretty,'') ||
      CASE WHEN COALESCE(vci.treatments_pretty_effective,'') <> '' THEN
             CASE WHEN COALESCE(vci.clutch_genotype_pretty,'') <> '' THEN ' + ' ELSE '' END
           ELSE '' END ||
      COALESCE(vci.treatments_pretty_effective,'')
  )                                                  AS genotype_treatment_rollup_effective,
  COALESCE(vci.created_by_instance,'')               AS created_by_instance,
  vci.created_at_instance,
  COALESCE(NULLIF(vci.clutch_name,''), vci.clutch_code)  AS clutch_label,
  COALESCE(NULLIF(vci.clutch_genotype_pretty,''), vci.treatments_pretty_effective, '') AS genotype_label,
  ''::text                                           AS parent_genotype_pretty
FROM public.v_clutch_instances vci
ORDER BY vci.clutch_code;

COMMIT;
