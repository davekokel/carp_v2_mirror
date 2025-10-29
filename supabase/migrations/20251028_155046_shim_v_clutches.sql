BEGIN;

DROP VIEW IF EXISTS public.v_clutches;

CREATE VIEW public.v_clutches AS
SELECT *
FROM public.v_clutch_instances;

COMMIT;
