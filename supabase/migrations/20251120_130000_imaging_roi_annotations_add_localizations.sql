BEGIN;

ALTER TABLE public.imaging_roi_annotations
  ADD COLUMN IF NOT EXISTS genotype_marker_localizations text,
  ADD COLUMN IF NOT EXISTS treatment_marker_localizations text;

COMMIT;
