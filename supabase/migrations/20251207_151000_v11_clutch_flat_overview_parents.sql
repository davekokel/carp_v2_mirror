BEGIN;

DROP VIEW IF EXISTS public.v11_clutch_flat_overview_parents;

CREATE VIEW public.v11_clutch_flat_overview_parents AS
SELECT
  cf.*
FROM public.v11_clutch_flat_overview cf;

COMMENT ON VIEW public.v11_clutch_flat_overview_parents IS
'v11 clutch flat overview (placeholder parents view; currently pass-through to v11_clutch_flat_overview).';

COMMIT;
