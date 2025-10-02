DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treatments' AND column_name='treatment_code'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treatments' AND column_name='treatment_type'
  ) THEN
    EXECUTE 'ALTER TABLE public.treatments RENAME COLUMN treatment_code TO treatment_type';
  END IF;
END$$;

CREATE OR REPLACE VIEW public.v_fish_treatment_summary AS
SELECT
  ft.fish_id,
  f.fish_code,
  (t.treatment_type::text) AS treatment_type,
  (t.treatment_type::text) AS treatment_name,
  NULL::treatment_route AS route,
  ft.applied_at          AS started_at,
  NULL::timestamptz      AS ended_at,
  NULL::numeric          AS dose,
  NULL::treatment_unit   AS unit,
  NULL::text             AS vehicle
FROM public.fish_treatments ft
JOIN public.fish f ON f.id_uuid = ft.fish_id
JOIN public.treatments t ON t.id_uuid = ft.treatment_id;
