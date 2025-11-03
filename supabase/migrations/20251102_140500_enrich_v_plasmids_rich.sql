BEGIN;
DROP VIEW IF EXISTS public.v_plasmids_rich;
CREATE VIEW public.v_plasmids_rich AS
SELECT * FROM public.plasmids;
COMMIT;
