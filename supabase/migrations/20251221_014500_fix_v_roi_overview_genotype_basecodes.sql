BEGIN;

CREATE OR REPLACE VIEW public.v_roi_overview AS
SELECT
  r.id::text AS roi_id,
  ps.plate_id,
  ps.plate_code,
  ps.experiment_date,
  ps.experiment_name,
  ps.plate_note,
  ps.slot_id,
  ps.slot_label,
  ps.slot_index,
  ps.slot_note,
  r.roi_index_within_slot,
  r.roi_code,
  r.roi_note_anatomy,
  r.roi_path,
  r.created_at,
  ps.clutch_code,
  tg.treated_clutch_code,
  ps.treat_code AS treatment_code,
  ps.treat_text AS treatment_text,
  ps.genotype_code,
  g.genotype_basecodes,
  ps.genotype_pretty,
  gms.genotype_tg_style,
  gms.genotype_fluortag_style,
  gms.genotype_fluororganelle_style,
  tg.treatment_label_tg_style AS label_tg_style,
  tg.treatment_label_fluortag_style AS label_fluortag_style,
  tg.treatment_label_fluororganelle_style AS label_fluororganelle_style
FROM public.imaging_roi_annotations r
LEFT JOIN public.v11_imaging_plate_slot_overview ps
  ON ps.slot_id::uuid = r.slot_id
LEFT JOIN public.genotypes_v11 g
  ON g.genotype_code = ps.genotype_code
LEFT JOIN public.v11_treated_clutch_genotype_star_labels tg
  ON tg.genotype_code = ps.genotype_code
LEFT JOIN public.v_genotype_marker_styles_strict gms
  ON gms.genotype_code = ps.genotype_code
ORDER BY
  ps.experiment_date DESC NULLS LAST,
  ps.plate_code,
  ps.slot_index,
  r.roi_index_within_slot;

COMMIT;
