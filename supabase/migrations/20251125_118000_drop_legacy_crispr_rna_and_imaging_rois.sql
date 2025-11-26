BEGIN;

-- Drop truly legacy construct tables that are not used in v10 pipelines
DROP TABLE IF EXISTS public.rnas_legacy CASCADE;
DROP TABLE IF EXISTS public.crisprs_legacy CASCADE;

-- Drop old imaging ROI/file tables (v10 uses imaging_roi_annotations instead)
DROP TABLE IF EXISTS public.imaging_roi_files CASCADE;
DROP TABLE IF EXISTS public.imaging_rois CASCADE;

COMMIT;
