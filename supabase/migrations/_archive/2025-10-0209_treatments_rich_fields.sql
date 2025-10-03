DO $MAIN$
DECLARE
  have_all boolean;
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

  -- add nullable columns to fish_treatments if missing
  BEGIN
    ALTER TABLE public.fish_treatments
      ADD COLUMN IF NOT EXISTS dose numeric,
      ADD COLUMN IF NOT EXISTS unit text,
      ADD COLUMN IF NOT EXISTS vehicle text,
      ADD COLUMN IF NOT EXISTS ended_at timestamptz;
  EXCEPTION WHEN undefined_table THEN
    RETURN;
  END;

  -- add simple check constraint (idempotent)
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'ft_end_after_start'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish_treatments
             ADD CONSTRAINT ft_end_after_start
             CHECK (ended_at IS NULL OR ended_at >= applied_at)';
  END IF;

  -- (re)create summary view
  EXECUTE $V$
    CREATE OR REPLACE VIEW public.v_fish_treatment_summary AS
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
$MAIN$;
