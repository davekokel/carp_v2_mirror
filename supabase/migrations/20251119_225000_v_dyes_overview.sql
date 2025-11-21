BEGIN;

CREATE OR REPLACE VIEW public.v_dyes_overview AS
SELECT
  d.id,
  d.dye_base_code,
  d.name,
  d.notes,
  d.created_at
FROM public.dyes d
ORDER BY d.dye_base_code, d.name;

COMMIT;
