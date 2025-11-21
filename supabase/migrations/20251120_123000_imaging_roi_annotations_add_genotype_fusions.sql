BEGIN;

ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS genotype_marker_fusion_labels text;

COMMIT;
