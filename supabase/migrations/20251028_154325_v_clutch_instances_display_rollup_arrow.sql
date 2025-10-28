BEGIN;
CREATE OR REPLACE VIEW public.v_clutch_instances_display
(clutch_code, clutch_birthday, cross_name_pretty, clutch_name,
 clutch_genotype_pretty, clutch_strain_pretty, treatments_count_effective,
 treatments_pretty_effective, genotype_treatment_rollup_effective,
 created_by_instance, created_at_instance,
 clutch_label, genotype_label) AS
SELECT
  v.clutch_code,
  v.clutch_birthday,
  COALESCE(v.cross_name_pretty, ''),
  COALESCE(v.clutch_name, ''),
  COALESCE(v.clutch_genotype_pretty, ''),
  COALESCE(v.clutch_strain_pretty, ''),
  COALESCE(v.treatments_count_effective, 0)::int,
  COALESCE(v.treatments_pretty_effective, ''),
  /* exact format: treatments > genotype */
  CASE
    WHEN COALESCE(v.treatments_pretty_effective,'') <> '' AND COALESCE(v.clutch_genotype_pretty,'') <> ''
      THEN v.treatments_pretty_effective || ' > ' || v.clutch_genotype_pretty
    WHEN COALESCE(v.treatments_pretty_effective,'') <> ''
      THEN v.treatments_pretty_effective
    WHEN COALESCE(v.clutch_genotype_pretty,'') <> ''
      THEN v.clutch_genotype_pretty
    ELSE ''
  END,
  COALESCE(v.created_by_instance,''),
  v.created_at_instance,
  COALESCE(NULLIF(v.clutch_name,''), v.clutch_code) AS clutch_label,
  COALESCE(NULLIF(v.clutch_genotype_pretty,''), v.treatments_pretty_effective, '') AS genotype_label
FROM public.v_clutch_instances v;
COMMIT;
