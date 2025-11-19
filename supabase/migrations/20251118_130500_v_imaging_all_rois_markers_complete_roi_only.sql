BEGIN;

DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_complete_roi_only;

CREATE VIEW public.v_imaging_all_rois_markers_complete_roi_only AS
SELECT *
FROM public.v_imaging_all_rois_markers_complete
WHERE data_path IS NOT NULL;

COMMIT;
