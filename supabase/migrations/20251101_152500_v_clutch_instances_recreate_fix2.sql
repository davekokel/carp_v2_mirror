BEGIN;
DROP VIEW IF EXISTS public.v_clutch_instances;
CREATE VIEW public.v_clutch_instances AS
SELECT * FROM public.v_clutch_instances_base;
COMMIT;
