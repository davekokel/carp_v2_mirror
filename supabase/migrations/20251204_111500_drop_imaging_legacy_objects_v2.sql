BEGIN;

-- ───────── legacy imaging TABLES ─────────

-- Legacy clutch/genotype table (already marked LEGACY).
DROP TABLE IF EXISTS public.clutch_expected_genotypes_v11_legacy;

-- Old imaging clutch table (superseded by imaging_clutch_memberships).
DROP TABLE IF EXISTS public.imaging_clutches;

-- Old linkage table between imaging datasets and clutches (v9/v10 era).
DROP TABLE IF EXISTS public.imaging_dataset_clutch_linkage;

-- ───────── legacy imaging VIEWS (that are NOT referenced) ─────────

-- These are top-level legacy overviews that do not feed v11 views
-- (except v_imaging_clutches_rois, which we keep for now).
DROP VIEW IF EXISTS public.v_imaging_clutch_overview;
DROP VIEW IF EXISTS public.v_imaging_clutches_overview;
-- KEEP v_imaging_clutches_rois for now; v11_imaging_clutch_parent_star depends on it.
-- DROP VIEW IF EXISTS public.v_imaging_clutches_rois;

DROP VIEW IF EXISTS public.v_imaging_dataset_overview;
DROP VIEW IF EXISTS public.v_imaging_plate_slot_old;
DROP VIEW IF EXISTS public.v_imaging_plate_slot_simple;
DROP VIEW IF EXISTS public.v_imaging_clutch_parent_old;
DROP VIEW IF EXISTS public.v_roi_overview_old;

COMMIT;
