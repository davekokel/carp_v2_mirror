BEGIN;

-- Drop v10 fish overview views now that v11_fish_instance_star is table-based.

DROP VIEW IF EXISTS public.v10_fish_instances_overview_enriched;
DROP VIEW IF EXISTS public.v10_fish_instances_overview;
DROP VIEW IF EXISTS public.v10_fish_lines_overview;

COMMIT;
