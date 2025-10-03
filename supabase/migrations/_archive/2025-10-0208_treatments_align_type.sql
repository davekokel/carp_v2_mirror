DO $MAIN$
DECLARE
  have_all boolean;
  have_code boolean;
  have_type boolean;
BEGIN
  SELECT (
    SELECT count(*) FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname='public' AND c.relname IN ('fish_treatments','treatments','fish')
  ) = 3
  INTO have_all;

  IF NOT have_all THEN
    RETURN;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treatments' AND column_name='treatment_code'
  ) INTO have_code;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treatments' AND column_name='treatment_type'
  ) INTO have_type;

  IF have_code AND NOT have_type THEN
    EXECUTE 'ALTER TABLE public.treatments RENAME COLUMN treatment_code TO treatment_type';
  END IF;

  EXECUTE $V$
    CREATE OR REPLACE VIEW public.v_fish_treatment_summary AS
    SELECT
      ft.fish_id,
      f.fish_code,
      t.treatment_type::text AS treatment_type,
      t.treatment_type::text AS treatment_name,
      NULL::text            AS route,
      ft.applied_at         AS started_at,
      NULL::timestamptz     AS ended_at,
      NULL::numeric         AS dose,
      NULL::text            AS unit,
      NULL::text            AS vehicle
    FROM public.fish_treatments ft
    JOIN public.fish f ON f.id_uuid = ft.fish_id
    JOIN public.treatments t ON t.id_uuid = ft.treatment_id;
  $V$;
END
$MAIN$;
