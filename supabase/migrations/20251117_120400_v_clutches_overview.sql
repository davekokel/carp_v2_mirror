BEGIN;

DROP VIEW IF EXISTS public.v_clutches_overview;

CREATE VIEW public.v_clutches_overview AS
SELECT
  cl.id          AS clutch_id,
  cl.clutch_code,
  cl.clutch_date,
  CURRENT_DATE - cl.clutch_date AS clutch_age_days,

  cl.cross_id,
  vc.cross_run_code,

  vc.female_fish_id,
  vc.male_fish_id,
  vc.female_parent_code,
  vc.male_parent_code,

  vc.allele_cross_label,
  vc.allele_priority_cross_label,
  vc.genotype_cross_label,
  vc.base_code_cross_label,

  vc.treatment_cross_label,
  vc.treatment_fluor_cross_label,

  vc.all_base_codes_cross_label,
  vc.all_fluors_cross_label,

  cl.estimated_egg_count,
  cl.notes,
  cl.created_at

FROM public.clutches AS cl
LEFT JOIN public.v_crosses_overview AS vc
  ON vc.cross_id = cl.cross_id;

COMMIT;
