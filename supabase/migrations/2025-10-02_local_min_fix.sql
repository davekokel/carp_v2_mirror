-- Ensure pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ensure fish has id_uuid (skip if it already exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='id_uuid'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD COLUMN id_uuid uuid NOT NULL DEFAULT gen_random_uuid()';
    EXECUTE 'ALTER TABLE public.fish ADD PRIMARY KEY (id_uuid)';
  END IF;
END$$;

-- Ensure treatments has id_uuid (unique)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treatments' AND column_name='id_uuid'
  ) THEN
    EXECUTE 'ALTER TABLE public.treatments ADD COLUMN id_uuid uuid NOT NULL DEFAULT gen_random_uuid()';
  END IF;
END$$;

-- Make sure id_uuid is unique (ok even if it’s already PK)
CREATE UNIQUE INDEX IF NOT EXISTS treatments_id_uuid_key ON public.treatments(id_uuid);

-- (Re)create fish_treatments with FKs to fish(id_uuid) and treatments(id_uuid)
DROP TABLE IF EXISTS public.fish_treatments CASCADE;
CREATE TABLE public.fish_treatments (
  id_uuid      uuid NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  fish_id      uuid NOT NULL REFERENCES public.fish(id_uuid) ON DELETE CASCADE,
  treatment_id uuid NOT NULL REFERENCES public.treatments(id_uuid),
  applied_at   timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  created_by   text
);

-- Rebuild the summary view
DROP VIEW IF EXISTS public.v_fish_treatment_summary;
CREATE VIEW public.v_fish_treatment_summary AS
SELECT
  ft.fish_id,
  f.fish_code,
  t.treatment_type::text AS treatment_type,
  t.treatment_type::text AS treatment_name,
  NULL::treatment_route  AS route,
  ft.applied_at          AS started_at,
  NULL::timestamptz      AS ended_at,
  NULL::numeric          AS dose,
  NULL::text             AS vehicle
FROM public.fish_treatments ft
JOIN public.fish f        ON f.id_uuid = ft.fish_id
JOIN public.treatments t  ON t.id_uuid = ft.treatment_id;
