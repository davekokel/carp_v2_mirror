BEGIN;
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;
CREATE VIEW public.vw_fish_overview_with_label AS
SELECT * FROM public.v_fish_overview;
COMMIT;
