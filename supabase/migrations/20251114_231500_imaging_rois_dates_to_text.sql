BEGIN;

ALTER TABLE public.imaging_rois
  ALTER COLUMN date_experiment TYPE text USING date_experiment::text;

ALTER TABLE public.imaging_rois
  ALTER COLUMN date_mount TYPE text USING date_mount::text;

COMMIT;
