BEGIN;

DROP VIEW IF EXISTS public.v_clutches_for_entry;

CREATE VIEW public.v_clutches_for_entry AS
SELECT *
FROM public.v_clutch_instances
ORDER BY clutch_code;

COMMIT;
