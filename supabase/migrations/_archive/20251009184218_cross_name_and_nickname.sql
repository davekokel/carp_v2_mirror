BEGIN;

-- 1) Add columns if missing
ALTER TABLE public.crosses
  ADD COLUMN IF NOT EXISTS cross_name     text,
  ADD COLUMN IF NOT EXISTS cross_nickname text;

-- 2) Simple, robust name generator: "MOM_CODE × DAD_CODE"
CREATE OR REPLACE FUNCTION public.gen_cross_name(mom text, dad text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT
    trim(coalesce(NULLIF(mom, ''), '?')) || ' × ' ||
    trim(coalesce(NULLIF(dad, ''), '?'));
$$;

-- 3) Trigger: on INSERT, fill cross_name; default nickname = name if empty
CREATE OR REPLACE FUNCTION public.trg_cross_name_fill()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF NEW.cross_name IS NULL OR btrim(NEW.cross_name) = '' THEN
    NEW.cross_name := public.gen_cross_name(NEW.mother_code, NEW.father_code);
  END IF;

  IF NEW.cross_nickname IS NULL OR btrim(NEW.cross_nickname) = '' THEN
    NEW.cross_nickname := NEW.cross_name;
  END IF;

  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS trg_cross_name_fill ON public.crosses;
CREATE TRIGGER trg_cross_name_fill
BEFORE INSERT ON public.crosses
FOR EACH ROW EXECUTE FUNCTION public.trg_cross_name_fill();

-- 4) One-off backfill for existing rows
UPDATE public.crosses x
SET cross_name =
      COALESCE(x.cross_name, public.gen_cross_name(x.mother_code, x.father_code)),
    cross_nickname =
      COALESCE(x.cross_nickname,
               COALESCE(x.cross_name, public.gen_cross_name(x.mother_code, x.father_code)));

COMMIT;
