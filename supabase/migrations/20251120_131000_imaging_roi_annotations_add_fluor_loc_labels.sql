BEGIN;

ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS genotype_marker_fluor_loc_labels   text,
  ADD COLUMN IF NOT EXISTS treatment_marker_fluor_loc_labels  text,
  ADD COLUMN IF NOT EXISTS all_marker_fluor_loc_labels        text;

COMMIT;
