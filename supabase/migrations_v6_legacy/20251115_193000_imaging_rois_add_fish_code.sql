BEGIN;

ALTER TABLE public.imaging_rois
  ADD COLUMN fish_code text;

-- Optional: index to make backfill and lookups faster
CREATE INDEX IF NOT EXISTS idx_imaging_rois_fish_code
  ON public.imaging_rois (fish_code);

COMMIT;
