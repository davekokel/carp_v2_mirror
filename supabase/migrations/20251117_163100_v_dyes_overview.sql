CREATE OR REPLACE VIEW public.v_dyes_overview AS
SELECT
  d.id,
  d.dye_base_code,
  COALESCE(d.name, '')  AS name,
  COALESCE(d.notes, '') AS notes,
  d.created_at
FROM public.dyes d;
