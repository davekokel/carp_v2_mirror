BEGIN;

CREATE TABLE IF NOT EXISTS public.treated_clutches (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  treated_clutch_code text NOT NULL,
  clutch_instance_id  uuid NOT NULL REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
  label               text,
  created_by          text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

-- human-friendly code: TCI-YYYYMMDD-000001
CREATE SEQUENCE IF NOT EXISTS public.seq_treated_clutch_code;

CREATE OR REPLACE FUNCTION public.treated_clutch_code_next()
RETURNS text
LANGUAGE sql
AS $$
  SELECT 'TCI-'||to_char(now(),'YYYYMMDD')||'-'||lpad(nextval('public.seq_treated_clutch_code')::text, 6, '0');
$$;

CREATE OR REPLACE FUNCTION public.treated_clutches_bi_assign_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.treated_clutch_code IS NULL OR NEW.treated_clutch_code = '' THEN
    NEW.treated_clutch_code := public.treated_clutch_code_next();
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_treated_clutches_bi_assign_code ON public.treated_clutches;
CREATE TRIGGER trg_treated_clutches_bi_assign_code
BEFORE INSERT ON public.treated_clutches
FOR EACH ROW
EXECUTE FUNCTION public.treated_clutches_bi_assign_code();

-- keep codes unique
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.treated_clutches'::regclass AND conname='uq_treated_clutch_code'
  ) THEN
    EXECUTE 'ALTER TABLE public.treated_clutches ADD CONSTRAINT uq_treated_clutch_code UNIQUE (treated_clutch_code)';
  END IF;
END$$;

COMMIT;
