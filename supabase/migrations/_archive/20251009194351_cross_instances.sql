BEGIN;
CREATE TABLE IF NOT EXISTS public.cross_instances (
  id_uuid uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cross_id uuid NOT NULL REFERENCES public.crosses(id_uuid) ON DELETE CASCADE,
  cross_date date NOT NULL DEFAULT current_date,
  mother_tank_id uuid NULL REFERENCES public.containers(id_uuid),
  father_tank_id uuid NULL REFERENCES public.containers(id_uuid),
  note text NULL,
  created_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  cross_run_code text
);
CREATE SEQUENCE IF NOT EXISTS public.cross_run_code_seq START 10000;
CREATE OR REPLACE FUNCTION public.gen_cross_run_code() RETURNS text LANGUAGE plpgsql AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.cross_run_code_seq') INTO n; RETURN format('XR-%s%05s', y, n); END;
$$;
CREATE OR REPLACE FUNCTION public.trg_cross_run_code() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF NEW.cross_run_code IS NULL OR btrim(NEW.cross_run_code)='' THEN NEW.cross_run_code:=public.gen_cross_run_code(); END IF; RETURN NEW; END;
$$;
DROP TRIGGER IF EXISTS trg_cross_run_code ON public.cross_instances;
CREATE TRIGGER trg_cross_run_code BEFORE INSERT ON public.cross_instances FOR EACH ROW EXECUTE FUNCTION public.trg_cross_run_code();

-- clutches link to run as well as concept
ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS cross_instance_id uuid NULL REFERENCES public.cross_instances(id_uuid) ON DELETE SET NULL;
COMMIT;
