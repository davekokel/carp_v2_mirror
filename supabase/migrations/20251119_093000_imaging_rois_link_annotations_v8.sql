BEGIN;

-- v8: imaging_rois future-proofing
-- For now we only ensure an annotation_id column exists, but we do NOT
-- add a foreign key, because imaging_roi_annotations has no unique PK
-- column for individual ROIs yet (slot_id is many-to-one).

ALTER TABLE public.imaging_rois
  ADD COLUMN IF NOT EXISTS annotation_id uuid;

-- If any old FKs exist from earlier experiments, drop them so rebuilds are clean.
ALTER TABLE public.imaging_rois
  DROP CONSTRAINT IF EXISTS imaging_rois_annotation_id_fkey,
  DROP CONSTRAINT IF EXISTS fk_imaging_rois_m2annotation;

COMMIT;
