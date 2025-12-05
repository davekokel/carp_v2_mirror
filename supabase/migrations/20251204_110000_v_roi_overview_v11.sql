BEGIN;

-- Drop the old ROI overview view, if present
DROP VIEW IF EXISTS public.v_roi_overview;

-- Rebuild v_roi_overview using v_imaging_plate_slot_overview + ROI annotations.
CREATE VIEW public.v_roi_overview AS
WITH rois AS (
  SELECT
    ira.id::text                      AS roi_id,
    ira.slot_id::text                 AS slot_id,
    ira.roi_index_within_slot,
    ira.roi_code,
    ira.roi_note_anatomy,
    ira.roi_path,
    ira.created_at
  FROM public.imaging_roi_annotations ira
)
SELECT
  r.roi_id,
  ps.plate_code,
  ps.experiment_date,
  ps.experiment_name,
  ps.plate_note,
  ps.slot_label,
  ps.slot_index,
  ps.slot_note,
  r.roi_index_within_slot,
  r.roi_code,
  r.roi_note_anatomy,
  r.roi_path,
  r.created_at,
  -- v11 clutch / treatment / genotype labels from the slot overview
  ps.clutch_code,
  ps.treated_clutch_code,
  ps.treatment_code,
  ps.treatment_text,
  ps.genotype_code,
  ps.genotype_basecodes,
  ps.genotype_pretty,
  ps.genotype_tg_style,
  ps.genotype_fluortag_style,
  ps.genotype_fluororganelle_style,
  ps.label_tg_style,
  ps.label_fluortag_style,
  ps.label_fluororganelle_style
FROM rois r
LEFT JOIN public.v_imaging_plate_slot_overview ps
  ON ps.slot_id = r.slot_id
ORDER BY
  ps.experiment_date DESC NULLS LAST,
  ps.plate_code,
  ps.slot_index,
  r.roi_index_within_slot;

COMMIT;
