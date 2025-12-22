BEGIN;

-- These legacy ROI views were part of the earlier ROI stack and may still exist on some DBs.
-- They depend on v_genotype_marker_styles_strict, so drop them first.
DROP VIEW IF EXISTS public.v_roi_overview_display_v6;
DROP VIEW IF EXISTS public.v_roi_overview_rollups;
DROP VIEW IF EXISTS public.v_roi_overview;

-- Now safe to drop marker-style helper views.
DROP VIEW IF EXISTS public.v_genotype_marker_styles_strict;
DROP VIEW IF EXISTS public.v_construct_marker_styles;

COMMIT;
