BEGIN;

DROP VIEW IF EXISTS public.fish_instances CASCADE;

CREATE VIEW public.fish_instances AS
SELECT *
FROM public.fish_instances_v10;

COMMENT ON VIEW public.fish_instances IS
  'Stable view for fish instances (currently backed by fish_instances_v10).';

COMMIT;
