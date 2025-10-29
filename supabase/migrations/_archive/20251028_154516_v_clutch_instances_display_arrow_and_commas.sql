BEGIN;

CREATE OR REPLACE VIEW public.v_clutch_instances_display
(clutch_code, clutch_birthday, cross_name_pretty, clutch_name,
 clutch_genotype_pretty, clutch_strain_pretty, treatments_count_effective,
 treatments_pretty_effective, genotype_treatment_rollup_effective,
 created_by_instance, created_at_instance,
 clutch_label, genotype_label) AS
WITH src AS (
  SELECT
    v.*,
    /* normalize legacy ' + ' lists to ', ' for display only */
    NULLIF(
      REGEXP_REPLACE(REPLACE(COALESCE(v.treatments_pretty_effective,''), ' + ', ', '), '\s+', ' ', 'g'),
      ''
    ) AS t_clean
  FROM public.v_clutch_instances v
)
SELECT
  s.clutch_code,
  s.clutch_birthday,
  COALESCE(s.cross_name_pretty, ''),
  COALESCE(s.clutch_name, ''),
  COALESCE(s.clutch_genotype_pretty, ''),
  COALESCE(s.clutch_strain_pretty, ''),
  COALESCE(s.treatments_count_effective, 0)::int,
  /* keep original for backwards compatibility */
  COALESCE(s.treatments_pretty_effective, ''),
  /* exact format: treatments, treatments > genotype (arrow only if both) */
  CASE
    WHEN s.t_clean IS NOT NULL AND s.clutch_genotype_pretty <> ''
      THEN s.t_clean || ' > ' || s.clutch_genotype_pretty
    WHEN s.t_clean IS NOT NULL
      THEN s.t_clean
    WHEN s.clutch_genotype_pretty <> ''
      THEN s.clutch_genotype_pretty
    ELSE ''
  END AS genotype_treatment_rollup_effective,
  COALESCE(s.created_by_instance,''),
  s.created_at_instance,
  COALESCE(NULLIF(s.clutch_name,''), s.clutch_code) AS clutch_label,
  COALESCE(NULLIF(s.clutch_genotype_pretty,''), COALESCE(s.t_clean,'')) AS genotype_label
FROM src s;

COMMIT;
