BEGIN;

DROP VIEW IF EXISTS public.v11_dyes_star;

CREATE VIEW public.v11_dyes_star AS
SELECT
    d.id,
    d.dye_base_code,
    d.name,
    d.notes,
    d.created_at,
    f.fluor_code,
    f.fluor_name,
    f.excitation_nm,
    f.emission_nm
FROM public.dyes d
LEFT JOIN public.fluors f
  ON f.id = d.fluor_id;

COMMIT;
