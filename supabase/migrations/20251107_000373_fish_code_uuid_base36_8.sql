BEGIN;

-- Helper: full UUID→numeric, then reduce into 36^8 and encode to fixed 8 base36 chars
CREATE OR REPLACE FUNCTION public.uuid_to_base36_8(p uuid)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  hex text := replace(p::text, '-', '');
  n   numeric;
  base36_max numeric := 36^8; -- 36^8 = 2,821,109,907,456
  chars constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  out text := '';
  r   int;
BEGIN
  -- convert 128-bit hex → numeric
  EXECUTE format('SELECT (X''%s'')::bit(128)::numeric', hex) INTO n;

  -- map into the 36^8 space so we get exactly 8 base36 digits
  n := mod(n, base36_max);

  IF n IS NULL THEN
    n := 0;
  END IF;

  IF n = 0 THEN
    out := '0';
  END IF;

  WHILE n > 0 LOOP
    r := (n % 36)::int;
    out := substr(chars, r + 1, 1) || out;
    n := trunc(n / 36);
  END LOOP;

  -- fixed width 8, zero-padded, uppercase
  RETURN lpad(upper(out), 8, '0');
END
$$;

-- Trigger: always normalize to FSH-<8 base36> if blank or decimal-like
CREATE OR REPLACE FUNCTION public.trg_set_fish_code_from_uuid_base36_8()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  code text := NULLIF(btrim(NEW.fish_code), '');
BEGIN
  IF NEW.id IS NULL THEN
    NEW.id := gen_random_uuid();
  END IF;

  -- set/normalize when missing OR decimal style like FSH-00000123
  IF code IS NULL OR code ~* '^FSH-\d+$' THEN
    NEW.fish_code := 'FSH-' || public.uuid_to_base36_8(NEW.id);
  END IF;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_fish_code_default ON public.fish;
CREATE TRIGGER trg_fish_code_default
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.trg_set_fish_code_from_uuid_base36_8();

-- Backfill existing decimal/blank codes to the new 8-char base36 format
UPDATE public.fish f
SET fish_code = 'FSH-' || public.uuid_to_base36_8(f.id)
WHERE (fish_code IS NULL OR fish_code ~* '^FSH-\d+$');

-- Optional: enforce format going forward (comment out if you want to defer)
ALTER TABLE public.fish DROP CONSTRAINT IF EXISTS ck_fish_code_format;
ALTER TABLE public.fish
  ADD CONSTRAINT ck_fish_code_format
  CHECK (fish_code ~* '^FSH-[0-9A-Z]{8}$');

COMMIT;
