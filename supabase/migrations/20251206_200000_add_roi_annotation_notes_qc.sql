BEGIN;

ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS annotation_notes text,
  ADD COLUMN IF NOT EXISTS qc_flag text;

COMMIT;
