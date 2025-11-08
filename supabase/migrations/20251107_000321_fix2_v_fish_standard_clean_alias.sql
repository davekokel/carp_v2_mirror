BEGIN;
DROP VIEW IF EXISTS public.v_fish_standard_clean;
CREATE VIEW public.v_fish_standard_clean AS
SELECT * FROM public.v_fish_main;
COMMIT;
