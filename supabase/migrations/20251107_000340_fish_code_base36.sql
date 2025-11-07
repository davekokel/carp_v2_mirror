BEGIN;

-- 1) Unique code column (if not already enforced)
ALTER TABLE public.fish
  ADD CONSTRAINT uq_fish_code UNIQUE (fish_code);

-- 2) Monotonic sequence for codes
CREATE SEQUENCE IF NOT EXISTS public.seq_fish_code;

-- 3) Base36 encoder (0-9 A-Z), upper-case, no leading sign
CREATE OR REPLACE FUNCTION public.to_base36(n BIGINT)
RETURNS text
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE
  v BIGINT := n;
  d INT;
  out TEXT := '';
  alphabet TEXT := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
BEGIN
  IF v < 0 THEN
    RAISE EXCEPTION 'to_base36: negative not supported';
  END IF;
  IF v = 0 THEN
    RETURN '0';
  END IF;
  WHILE v > 0 LOOP
    d := (v % 36)::INT;
    out := substr(alphabet, d+1, 1) || out;
    v := v / 36;
  END LOOP;
  RETURN out;
END
$$;

-- 4) Code generator: FSH- + 8-char, zero-padded base36 from sequence
CREATE OR REPLACE FUNCTION public.make_fish_code()
RETURNS text
LANGUAGE sql VOLATILE AS $$
  SELECT 'FSH-' ||
         lpad(public.to_base36(nextval('public.seq_fish_code')), 8, '0');
$$;

-- 5) Trigger to auto-fill on insert if code is NULL/blank
CREATE OR REPLACE FUNCTION public.fish_code_default_trg()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.fish_code IS NULL OR btrim(NEW.fish_code) = '' THEN
    NEW.fish_code := public.make_fish_code();
  END IF;
  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_fish_code_default ON public.fish;
CREATE TRIGGER trg_fish_code_default
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.fish_code_default_trg();

-- 6) One-time backfill existing rows that have blank codes
WITH to_fix AS (
  SELECT id FROM public.fish WHERE fish_code IS NULL OR btrim(fish_code) = ''
)
UPDATE public.fish f
SET fish_code = public.make_fish_code()
FROM to_fix x
WHERE f.id = x.id;

COMMIT;
