BEGIN;
/* Contract view for UI pickers (annotation + mounts).
   Stable column order; includes mom/dad fish codes for searching. */
CREATE OR REPLACE VIEW public.v_clutches_for_entry AS
SELECT
  v.clutch_code,
  v.cross_name_pretty,
  v.clutch_name,
  v.clutch_genotype_pretty,
  v.genotype_treatment_rollup_effective,
  v.treatments_count_effective,
  v.treatments_pretty_effective,
  v.clutch_birthday,
  v.created_by_instance,
  v.created_at_instance,
  cci.mom_fish_code,
  cci.dad_fish_code
FROM public.v_clutch_instances_display v
LEFT JOIN public.v_cross_clutch_instances cci
  ON cci.clutch_code = v.clutch_code;
COMMIT;
