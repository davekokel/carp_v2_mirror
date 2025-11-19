BEGIN;

CREATE OR REPLACE VIEW public.v_roi_overview AS
SELECT
  *
FROM public.imaging_rois;

COMMIT;
