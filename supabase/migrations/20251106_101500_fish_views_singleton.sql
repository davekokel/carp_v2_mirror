BEGIN;

-- Keep ONLY: v_fish_overview_id (canonical), and the marker/genotype helper views it depends on.
-- Drop legacy/overlapping fish views outright.
DROP VIEW IF EXISTS public.v_fish CASCADE;
DROP VIEW IF EXISTS public.v_fish_rich CASCADE;
DROP VIEW IF EXISTS public.v_fish_rich_base CASCADE;
DROP VIEW IF EXISTS public.v_fish_genotypes_pretty CASCADE;
DROP VIEW IF EXISTS public.v_fish_name_from_genotype CASCADE;

COMMENT ON VIEW public.v_fish_overview_id IS
'CANON: single fish overview (PK-based): genotype + fluorescent rollups. All pages should query this.';

COMMIT;
