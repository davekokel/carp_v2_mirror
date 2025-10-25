BEGIN;
ALTER TABLE public.clutches ADD COLUMN IF NOT EXISTS clutch_instance_code text;
CREATE UNIQUE INDEX IF NOT EXISTS uq_clutches_instance_code ON public.clutches (
    clutch_instance_code
) WHERE clutch_instance_code IS NOT NULL;
CREATE SEQUENCE IF NOT EXISTS public.clutch_instance_code_seq START 10000;
CREATE OR REPLACE FUNCTION public.gen_clutch_instance_code() RETURNS text LANGUAGE plpgsql AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.clutch_instance_code_seq') INTO n; RETURN format('CI-%s%05s', y, n); END;
$$;
CREATE OR REPLACE FUNCTION public.trg_clutch_instance_code() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF NEW.clutch_instance_code IS NULL OR btrim(NEW.clutch_instance_code)='' THEN NEW.clutch_instance_code:=public.gen_clutch_instance_code(); END IF; RETURN NEW; END;
$$;
DROP TRIGGER IF EXISTS trg_clutch_instance_code ON public.clutches;
CREATE TRIGGER trg_clutch_instance_code BEFORE INSERT ON public.clutches FOR EACH ROW EXECUTE FUNCTION public.trg_clutch_instance_code();
COMMIT;
