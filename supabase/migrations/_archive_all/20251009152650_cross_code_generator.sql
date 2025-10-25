BEGIN;

-- 1) Sequence for compact incremental codes
CREATE SEQUENCE IF NOT EXISTS public.cross_code_seq START 10000;

-- 2) Function: returns something like CR-250001
CREATE OR REPLACE FUNCTION public.gen_cross_code()
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
  y text := to_char(current_date,'YY');
  n bigint;
BEGIN
  SELECT nextval('public.cross_code_seq') INTO n;
  RETURN format('CR-%s%05s', y, n);
END;
$$;

-- 3) Trigger: fill in cross_code automatically on insert
CREATE OR REPLACE FUNCTION public.trg_cross_code()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.cross_code IS NULL OR btrim(NEW.cross_code) = '' THEN
    NEW.cross_code := public.gen_cross_code();
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_cross_code ON public.crosses;
CREATE TRIGGER trg_cross_code
BEFORE INSERT ON public.crosses
FOR EACH ROW EXECUTE FUNCTION public.trg_cross_code();

COMMIT;
