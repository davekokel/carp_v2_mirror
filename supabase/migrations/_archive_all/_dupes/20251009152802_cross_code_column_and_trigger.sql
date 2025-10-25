BEGIN;

-- 1) Add the column if missing
ALTER TABLE public.crosses
ADD COLUMN IF NOT EXISTS cross_code text;

-- Optional: keep codes unique when present
CREATE UNIQUE INDEX IF NOT EXISTS uq_crosses_cross_code
ON public.crosses (cross_code)
WHERE cross_code IS NOT NULL;

-- 2) Sequence to generate compact incremental codes
CREATE SEQUENCE IF NOT EXISTS public.cross_code_seq START 10000;

-- 3) Function: e.g., CR-25xxxxx (YY + 5 digits)
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

-- 4) Trigger to fill cross_code on INSERT when blank
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

-- 5) Backfill existing rows that lack cross_code
UPDATE public.crosses
SET cross_code = public.gen_cross_code()
WHERE cross_code IS NULL OR btrim(cross_code) = '';

COMMIT;
