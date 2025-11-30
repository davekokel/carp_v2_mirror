BEGIN;

-- Drop the global UNIQUE(roi_code) index; we now enforce per-slot uniqueness.
DROP INDEX IF EXISTS public.imaging_roi_annotations_roi_code_unique;

COMMIT;
