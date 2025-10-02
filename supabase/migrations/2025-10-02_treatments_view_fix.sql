DROP VIEW IF EXISTS public.v_fish_treatment_summary;

CREATE VIEW public.v_fish_treatment_summary AS
SELECT
  ft.fish_id,
  f.fish_code,
  COALESCE(t.treatment_type::text, t.treatment_code::text) AS treatment_type,
  COALESCE(t.treatment_type::text, t.treatment_code::text) AS treatment_name,
  NULL::treatment_route    AS route,
  ft.applied_at            AS started_at,
  NULL::timestamptz        AS ended_at,
  NULL::numeric            AS dose,
  NULL::treatment_unit     AS unit,
  NULL::text               AS vehicle
FROM public.fish_treatments ft
JOIN public.fish f ON f.id_uuid = ft.fish_id
JOIN public.treatments t ON t.id_uuid = ft.treatment_id;
