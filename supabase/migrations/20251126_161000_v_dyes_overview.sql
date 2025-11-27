BEGIN;

DROP VIEW IF EXISTS public.v_dyes_overview;

CREATE VIEW public.v_dyes_overview AS
SELECT
  d.id::text      AS id,
  d.dye_base_code,
  d.name,
  d.notes,
  d.created_at,
  fl.fluor_code,
  fl.fluor_name,
  fl.excitation_nm,
  fl.emission_nm
FROM public.dyes d
LEFT JOIN public.fluors fl
  ON fl.id = d.fluor_id
ORDER BY d.dye_base_code, d.name;

COMMIT;
