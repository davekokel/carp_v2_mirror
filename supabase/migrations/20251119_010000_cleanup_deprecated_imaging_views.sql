BEGIN;

-- Drop deprecated imaging views if they exist. These were prototypes
-- that have been replaced by canonical imaging ROI + clutches paths.

DROP VIEW IF EXISTS public.v_imaging_treatments_markers CASCADE;
DROP VIEW IF EXISTS public.v_imaging_clutches_treatments CASCADE;
DROP VIEW IF EXISTS public.v_imaging_clutches_rois_inherited CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_complete CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_complete_roi_only CASCADE;

COMMIT;
