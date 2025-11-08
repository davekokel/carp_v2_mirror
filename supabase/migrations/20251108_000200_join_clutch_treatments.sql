BEGIN;

-- Normalizer (lower + trim + collapse inner whitespace)
CREATE OR REPLACE FUNCTION public._norm(s text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT regexp_replace(lower(coalesce(s,'')), '\s+', ' ', 'g')::text
$$;

-- Link table for clutch treatments
CREATE TABLE IF NOT EXISTS public.join_clutch_treatments (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_id     uuid NOT NULL REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
  treatment_type         text NOT NULL,
  treatment_code         text NOT NULL,
  treatment_name         text,
  notes                  text,
  created_by             text,
  created_at             timestamptz NOT NULL DEFAULT now(),
  -- normalized columns used by your page's ON CONFLICT clause
  treatment_type_norm    text NOT NULL,
  treatment_code_norm    text NOT NULL
);

-- BEFORE INSERT/UPDATE trigger to populate *_norm
CREATE OR REPLACE FUNCTION public.jct_bi_norm()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.treatment_type_norm := public._norm(NEW.treatment_type);
  NEW.treatment_code_norm := public._norm(NEW.treatment_code);
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_jct_bi_norm ON public.join_clutch_treatments;
CREATE TRIGGER trg_jct_bi_norm
BEFORE INSERT OR UPDATE ON public.join_clutch_treatments
FOR EACH ROW EXECUTE FUNCTION public.jct_bi_norm();

-- Uniqueness your page targets in its ON CONFLICT clause
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_clutch_treatments'::regclass
      AND conname='uq_jct_by_instance_kind_code'
  ) THEN
    EXECUTE 'ALTER TABLE public.join_clutch_treatments
             ADD CONSTRAINT uq_jct_by_instance_kind_code
             UNIQUE (clutch_instance_id, treatment_type_norm, treatment_code_norm)';
  END IF;
END$$;

-- Helpful index for lookups by instance
CREATE INDEX IF NOT EXISTS ix_jct_clutch_instance_id
  ON public.join_clutch_treatments (clutch_instance_id);

COMMIT;
