BEGIN;

ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS treatment_marker_fusion_labels text;

COMMIT;
