BEGIN;

ALTER TABLE public.imaging_roi_annotations
ADD COLUMN IF NOT EXISTS n_tiffs integer NOT NULL DEFAULT 0;

COMMIT;
