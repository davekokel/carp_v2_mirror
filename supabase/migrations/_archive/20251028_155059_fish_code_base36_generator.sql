-- 1) Sequence for fish codes (monotonic, survives restarts)
CREATE SEQUENCE IF NOT EXISTS public.fish_code_seq36;

-- 2) Base-36 encoder (0-9, A-Z)
CREATE OR REPLACE FUNCTION public.base36(n bigint)
RETURNS text
LANGUAGE plpgsql IMMUTABLE STRICT
AS $$
DECLARE
  digits text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  q bigint := n;
  r int;
  out text := '';
BEGIN
  IF q IS NULL OR q < 0 THEN
    RAISE EXCEPTION 'base36(): n must be >= 0';
  END IF;
  IF q = 0 THEN
    RETURN '0';
  END IF;
  WHILE q > 0 LOOP
    r := (q % 36);
    out := substr(digits, r+1, 1) || out;
    q := q / 36;
  END LOOP;
  RETURN out;
END $$;

-- 3) Authoritative base-36 code: FSH-YY<base36(nextval)>
CREATE OR REPLACE FUNCTION public.gen_fish_code_base36(p_when timestamptz DEFAULT now())
RETURNS text
LANGUAGE sql STABLE
AS $$
  SELECT 'FSH-' || to_char($1, 'YY') || public.base36(nextval('public.fish_code_seq36'))
$$;

-- 4) Trigger function: set fish_code only if missing (BEFORE INSERT)
CREATE OR REPLACE FUNCTION public.fish_bi_set_fish_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.fish_code IS NULL OR trim(NEW.fish_code) = '' THEN
    NEW.fish_code := public.gen_fish_code_base36(now());
  END IF;
  RETURN NEW;
END $$;

-- 5) Replace existing BEFORE INSERT trigger on fish with our function
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
             WHERE c.relname='fish' AND t.tgname='bi_set_fish_code') THEN
    DROP TRIGGER bi_set_fish_code ON public.fish;
  END IF;
END$$;

CREATE TRIGGER bi_set_fish_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_bi_set_fish_code();
