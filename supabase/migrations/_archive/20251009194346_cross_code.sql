BEGIN;
ALTER TABLE public.crosses ADD COLUMN IF NOT EXISTS cross_code text;
CREATE UNIQUE INDEX IF NOT EXISTS uq_crosses_cross_code ON public.crosses(cross_code) WHERE cross_code IS NOT NULL;
CREATE SEQUENCE IF NOT EXISTS public.cross_code_seq START 10000;
CREATE OR REPLACE FUNCTION public.gen_cross_code() RETURNS text LANGUAGE plpgsql AS $$
DECLARE y text := to_char(current_date,'YY'); n bigint;
BEGIN SELECT nextval('public.cross_code_seq') INTO n; RETURN format('CR-%s%05s', y, n); END;
$$;
CREATE OR REPLACE FUNCTION public.trg_cross_code() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN IF NEW.cross_code IS NULL OR btrim(NEW.cross_code)='' THEN NEW.cross_code:=public.gen_cross_code(); END IF; RETURN NEW; END;
$$;
DROP TRIGGER IF EXISTS trg_cross_code ON public.crosses;
CREATE TRIGGER trg_cross_code BEFORE INSERT ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code();
-- cross_name / cross_nickname
ALTER TABLE public.crosses ADD COLUMN IF NOT EXISTS cross_name text, ADD COLUMN IF NOT EXISTS cross_nickname text;
CREATE OR REPLACE FUNCTION public.gen_cross_name(mom text, dad text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT trim(coalesce(NULLIF(mom,''),'?')) || ' × ' || trim(coalesce(NULLIF(dad,''),'?'));
$$;
CREATE OR REPLACE FUNCTION public.trg_cross_name_fill() RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN
  IF NEW.cross_name IS NULL OR btrim(NEW.cross_name)='' THEN NEW.cross_name:=public.gen_cross_name(NEW.mother_code,NEW.father_code); END IF;
  IF NEW.cross_nickname IS NULL OR btrim(NEW.cross_nickname)='' THEN NEW.cross_nickname:=NEW.cross_name; END IF;
  RETURN NEW;
END
$fn$;
DROP TRIGGER IF EXISTS trg_cross_name_fill ON public.crosses;
CREATE TRIGGER trg_cross_name_fill BEFORE INSERT ON public.crosses FOR EACH ROW EXECUTE FUNCTION public.trg_cross_name_fill();
COMMIT;
