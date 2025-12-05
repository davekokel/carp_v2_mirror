BEGIN;

-- Drop QA / transitional views that are no longer used in v11.
-- These are only referenced in earlier migrations and can be safely
-- removed now that we rely on v11_*_star / *_label views.

-- 1) Drop the duplicate/diagnostic views (in dependency order)
DROP VIEW IF EXISTS public.v11_fish_instance_duplicates_detail;
DROP VIEW IF EXISTS public.v11_fish_instance_duplicates;
DROP VIEW IF EXISTS public.v11_fish_instance_allele_keys;

-- 2) Drop the old compatibility views around genotypes
DROP VIEW IF EXISTS public.fish_genotypes_v11;
DROP VIEW IF EXISTS public.genotypes_v11_fish;

-- NOTE: We deliberately KEEP public.v11_line_allele_rollups.
-- It is used by:
--   - carp_app/ui/pages/270_🖨️_print_cross_and_clutch_labels.py
--   - scripts/v11_update_clutch_genotypes_from_parents.py
--   - v11_*_label migrations
-- It remains part of the v11 line/genotype stack.

COMMIT;
