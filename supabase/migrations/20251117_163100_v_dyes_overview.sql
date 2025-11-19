BEGIN;

DROP VIEW IF EXISTS public.v_dyes_overview;

CREATE VIEW public.v_dyes_overview AS
SELECT
  d.id,
  d.dye_base_code,
  d.name,
  d.notes,
  d.created_at
FROM public.dyes d;

COMMIT;
