BEGIN;

-- 1) Add column if missing
ALTER TABLE public.clutch_plans
  ADD COLUMN IF NOT EXISTS clutch_code text;

-- 2) Sequence for daily-ish incremental code (monotonic, not strictly per-day)
CREATE SEQUENCE IF NOT EXISTS public.seq_clutch_code;

-- 3) Generator: CL-YY + base32(seq) with zero pad (short + unique)
CREATE OR REPLACE FUNCTION public.gen_clutch_code()
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
  n bigint := nextval('public.seq_clutch_code');
  yy text := to_char(current_date, 'YY');
  alphabet text := '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
  x bigint := n;
  out text := '';
  r int;
BEGIN
  IF x = 0 THEN out := '0'; END IF;
  WHILE x > 0 LOOP
    r := (x % 32);
    out := substr(alphabet, r+1, 1) || out;
    x := x / 32;
  END LOOP;
  -- left-pad to 4 chars for readability
  WHILE length(out) < 4 LOOP
    out := '0' || out;
  END LOOP;
  RETURN 'CL-' || yy || out;
END$$;

-- 4) Trigger to assign code on insert if NULL
CREATE OR REPLACE FUNCTION public.trg_clutch_code()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.clutch_code IS NULL OR btrim(NEW.clutch_code) = '' THEN
    NEW.clutch_code := public.gen_clutch_code();
  END IF;
  RETURN NEW;
END$$;

DROP TRIGGER IF EXISTS trg_clutch_code ON public.clutch_plans;
CREATE TRIGGER trg_clutch_code
BEFORE INSERT ON public.clutch_plans
FOR EACH ROW
EXECUTE FUNCTION public.trg_clutch_code();

-- 5) Backfill any existing rows without a code
UPDATE public.clutch_plans
SET clutch_code = public.gen_clutch_code()
WHERE clutch_code IS NULL OR btrim(clutch_code) = '';

-- 6) Uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_plans_clutch_code
  ON public.clutch_plans(clutch_code);

COMMIT;
