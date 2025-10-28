BEGIN;
CREATE OR REPLACE VIEW public.v_clutch_instances_display AS
SELECT
  clutch_code,
  clutch_birthday,
  COALESCE(cross_name_pretty, '')                AS cross_name_pretty,
  COALESCE(clutch_name, '')                      AS clutch_name,
  COALESCE(clutch_genotype_pretty, '')           AS clutch_genotype_pretty,
  COALESCE(clutch_strain_pretty, '')             AS clutch_strain_pretty,
  COALESCE(treatments_count_effective, 0)::int   AS treatments_count_effective,
  COALESCE(treatments_pretty_effective, '')      AS treatments_pretty_effective,
  COALESCE(genotype_treatment_rollup_effective,
           NULLIF(clutch_genotype_pretty,'') ||
           CASE WHEN COALESCE(treatments_pretty_effective,'') <> '' THEN
                  CASE WHEN COALESCE(clutch_genotype_pretty,'') <> '' THEN ' + ' ELSE '' END
                ELSE '' END ||
           COALESCE(treatments_pretty_effective,'')
  )                                              AS genotype_treatment_rollup_effective,
  COALESCE(created_by_instance,'')               AS created_by_instance,
  created_at_instance
FROM public.v_clutch_instances;
COMMIT;
