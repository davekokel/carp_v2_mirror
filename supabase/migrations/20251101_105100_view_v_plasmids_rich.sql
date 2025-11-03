BEGIN;
DROP VIEW IF EXISTS public.v_plasmids_rich;
CREATE VIEW public.v_plasmids_rich AS
SELECT
  p.*
FROM public.plasmids p;
COMMIT;
