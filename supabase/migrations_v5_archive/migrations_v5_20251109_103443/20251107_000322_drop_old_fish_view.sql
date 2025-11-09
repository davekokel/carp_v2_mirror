BEGIN;
DROP VIEW IF EXISTS public.v_fish_standard_clean;
-- If you also want to ensure old callers break loudly:
-- DROP VIEW IF EXISTS public.v_fish_overview_id;
COMMIT;
