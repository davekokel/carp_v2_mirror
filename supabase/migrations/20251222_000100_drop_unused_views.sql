BEGIN;

-- Drop dependents of v11_clutch_parent_genotypes first
DROP VIEW IF EXISTS public.v11_clutch_expected_genotype_star;
DROP VIEW IF EXISTS public.v11_imaging_clutch_parent_star;

-- Now drop the shared dependency
DROP VIEW IF EXISTS public.v11_clutch_parent_genotypes;

-- The rest are independent
DROP VIEW IF EXISTS public.v11_clutch_allele_marker_style;
DROP VIEW IF EXISTS public.v11_clutch_flat_overview_parents;
DROP VIEW IF EXISTS public.v11_fish_allele_star;
DROP VIEW IF EXISTS public.v11_legacy_clutch_parents_pretty;
DROP VIEW IF EXISTS public.v_roi_overview_rollups_qc;

COMMIT;
