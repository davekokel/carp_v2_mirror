BEGIN;

-- 1) Drop views that depend on fish_groups / join_fish_group_alleles, if they exist.
--    (Names may vary; adjust if your actual view names differ.)
DROP VIEW IF EXISTS public.v_fish_groups_overview;
DROP VIEW IF EXISTS public.v11_fish_group_star;

-- 2) Remove fish_group_id from fish_lines (we now use genotype_v11_id instead).
--    Dropping the column automatically drops any FK constraints on it.
ALTER TABLE public.fish_lines
  DROP COLUMN IF EXISTS fish_group_id;

-- 3) Drop join table that hung alleles off fish_groups (superseded by join_line_alleles
--    and join_genotype_constructs_v11).
DROP TABLE IF EXISTS public.join_fish_group_alleles;

-- 4) Drop fish_groups itself. At this point no columns reference it.
--    If any ad-hoc views still depend on it, this will fail; in that case,
--    drop or update those views first and rerun this migration.
DROP TABLE IF EXISTS public.fish_groups;

COMMIT;
