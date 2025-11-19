BEGIN;

-- Optional: add source_system / import_batch_id to key imaging tables
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS source_system text,
  ADD COLUMN IF NOT EXISTS import_batch_id text;

ALTER TABLE public.treatments
  ADD COLUMN IF NOT EXISTS source_system text,
  ADD COLUMN IF NOT EXISTS import_batch_id text;

ALTER TABLE public.imaging_clutch_memberships
  ADD COLUMN IF NOT EXISTS source_system text,
  ADD COLUMN IF NOT EXISTS import_batch_id text;

-- Drop clearly experimental / intermediate imaging views, but keep core ones.
-- IMPORTANT: we intentionally DO NOT drop:
--   - v_roi_overview
--   - v_imaging_clutch_memberships_norm
--   - v_imaging_clutches_treatments
--   - v_imaging_clutches_rois
-- because they are currently wired into pages / scripts.

-- Legacy / experimental imaging chain variants
DROP VIEW IF EXISTS public.v_imaging_clutches_rois_fix           CASCADE;
DROP VIEW IF EXISTS public.v_imaging_clutches_rois_fix2          CASCADE;
DROP VIEW IF EXISTS public.v_imaging_clutches_rois_recreate      CASCADE;
DROP VIEW IF EXISTS public.v_imaging_clutches_rois_inherited     CASCADE;

-- Legacy ROI summaries
DROP VIEW IF EXISTS public.v_imaging_mem_histone_rois            CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers            CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_with_genotype CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_complete   CASCADE;
DROP VIEW IF EXISTS public.v_imaging_all_rois_markers_complete_roi_only CASCADE;

-- Legacy genotype/treatment scratch views
DROP VIEW IF EXISTS public.v_imaging_clutch_genotype_markers     CASCADE;
DROP VIEW IF EXISTS public.v_imaging_clutches_markers_rebuild    CASCADE;

COMMIT;
