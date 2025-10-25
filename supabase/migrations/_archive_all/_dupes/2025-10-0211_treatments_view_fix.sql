DO $$
DECLARE
  have_all boolean;
BEGIN
  SELECT (
    SELECT count(*) FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname='public' AND c.relname IN ('fish','fish_treatments','treatments')
  ) = 3 INTO have_all;

  IF NOT have_all THEN
    RETURN;
  END IF;

  EXECUTE $V$
    DROP VIEW IF EXISTS public.v_fish_treatment_summary;
    CREATE VIEW public.v_fish_treatment_summary AS
    SELECT
      ft.fish_id,
      f.fish_code,
      t.treatment_type::text AS treatment_type,
      t.treatment_type::text AS treatment_name,
      NULL::text            AS route,
      ft.applied_at         AS started_at,
      ft.ended_at,
      ft.dose,
      ft.unit,
      ft.vehicle
    FROM public.fish_treatments ft
    JOIN public.fish f ON f.id_uuid = ft.fish_id
    JOIN public.treatments t ON t.id_uuid = ft.treatment_id;
  $V$;
END
$$;
