BEGIN;
DROP VIEW IF EXISTS public.v_fish_overview_with_label;
CREATE VIEW public.v_fish_overview_with_label AS
SELECT * FROM public.v_fish_overview;
COMMIT;
