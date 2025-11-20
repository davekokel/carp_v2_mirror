BEGIN;

-- v8: link imaging_rois to imaging_roi_annotations so they sit in the main imaging spine

-- 1) ensure imaging_rois has an annotation_id column (nullable for now)
ALTER TABLE public.imaging_rois
  ADD COLUMN IF NOT EXISTS annotation_id uuid;

-- 2) drop any old FK on annotation_id, if present
ALTER TABLE public.imaging_rois
  DROP CONSTRAINT IF EXISTS imaging_rois_annotation_id_fkey,
  DROP CONSTRAINT IF EXISTS fk_imaging_rois_m2annotation;

-- 3) add canonical FK → imaging_roi_annotations(id)
ALTER TABLE public.imaging_rois
  ADD CONSTRAINT fk_imaging_rois_m2annotation
  FOREIGN KEY (annotation_id)
  REFERENCES public.imaging_roi_annotations(slot_id)  -- uses slot_id as the link
  ON UPDATE CASCADE
  ON DELETE SET NULL;

COMMIT;
