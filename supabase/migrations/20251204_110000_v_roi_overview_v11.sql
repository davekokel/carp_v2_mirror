BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview;

CREATE VIEW public.v_roi_overview AS
WITH rois AS (
    SELECT ira.id::text AS roi_id,
           ira.slot_id::text AS slot_id,
           ira.roi_index_within_slot,
           ira.roi_code,
           ira.roi_note_anatomy,
           ira.roi_path,
           ira.created_at
    FROM public.imaging_roi_annotations ira
)
SELECT
    r.roi_id,
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
    tg.genotype_basecodes,
    COALESCE(ps.genotype_pretty, tg.genotype_pretty) AS genotype_pretty,
    NULL::text AS genotype_tg_style,
    NULL::text AS genotype_fluortag_style,
    NULL::text AS genotype_fluororganelle_style,
    tg.treatment_label_tg_style        AS label_tg_style,
    tg.treatment_label_fluortag_style  AS label_fluortag_style,
    tg.treatment_label_fluororganelle_style AS label_fluororganelle_style
FROM rois r
LEFT JOIN public.v11_imaging_plate_slot_overview ps
  ON ps.slot_id = r.slot_id
LEFT JOIN public.v11_treated_clutch_genotype_star_labels tg
  ON tg.genotype_code = ps.genotype_code
ORDER BY
    ps.experiment_date DESC NULLS LAST,
    ps.plate_code,
    ps.slot_index,
    r.roi_index_within_slot;

COMMIT;
