BEGIN;

-- Drop legacy fish-related views if they exist
DROP VIEW IF EXISTS public.v_fish_instances_overview;
DROP VIEW IF EXISTS public.v_fish_overview;
DROP VIEW IF EXISTS public.v_fish_lines_overview;

-- Drop legacy fish tables if they exist
DROP TABLE IF EXISTS public.join_fish_transgene_alleles;
DROP TABLE IF EXISTS public.fish_instances;
DROP TABLE IF EXISTS public.fish;

COMMIT;
