BEGIN;
CREATE OR REPLACE VIEW public.v_clutch_instances_display
(clutch_code, clutch_birthday, cross_name_pretty, clutch_name,
 clutch_genotype_pretty, clutch_strain_pretty, treatments_count_effective,
 treatments_pretty_effective, genotype_treatment_rollup_effective,
 created_by_instance, created_at_instance,
 clutch_label, genotype_label) AS
SELECT
  clutch_code,
  clutch_birthday,
  COALESCE(cross_name_pretty, '')                AS cross_name_pretty,
  COALESCE(clutch_name, '')                      AS clutch_name,
  COALESCE(clutch_genotype_pretty, '')           AS clutch_genotype_pretty,
  COALESCE(clutch_strain_pretty, '')             AS clutch_strain_pretty,
  COALESCE(treatments_count_effective, 0)::int   AS treatments_count_effective,
  COALESCE(treatments_pretty_effective, '')      AS treatments_pretty_effective,
  COALESCE(
    genotype_treatment_rollup_effective,
    NULLIF(clutch_genotype_pretty,'') ||
      CASE WHEN COALESCE(treatments_pretty_effective,'') <> '' THEN
             CASE WHEN COALESCE(clutch_genotype_pretty,'') <> '' THEN ' + ' ELSE '' END
           ELSE '' END ||
      COALESCE(treatments_pretty_effective,'')
  )                                              AS genotype_treatment_rollup_effective,
  COALESCE(created_by_instance,'')               AS created_by_instance,
  created_at_instance,
  -- appended friendly columns (do not disturb existing positions)
  COALESCE(NULLIF(clutch_name,''), clutch_code)  AS clutch_label,
  COALESCE(NULLIF(clutch_genotype_pretty,''), treatments_pretty_effective, '') AS genotype_label
FROM public.v_clutch_instances;
COMMIT;
