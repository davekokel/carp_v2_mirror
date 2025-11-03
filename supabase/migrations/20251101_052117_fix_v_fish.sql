BEGIN;
DROP VIEW IF EXISTS public.v_fish;
CREATE VIEW public.v_fish AS
SELECT * FROM public.fish;
COMMIT;
