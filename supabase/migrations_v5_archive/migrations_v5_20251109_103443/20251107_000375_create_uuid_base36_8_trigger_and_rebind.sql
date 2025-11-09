BEGIN;

-- Ensure gen_random_uuid() is available
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Helper: robust 8-char base36 derived from UUID via byte-wise modulo
CREATE OR REPLACE FUNCTION public.uuid_to_base36_8(p uuid)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  b bytea := decode(replace(p::text, '-', ''), 'hex');  -- 16 bytes
  m bigint := 36^8;                                     -- 2,821,109,907,456
  rem bigint := 0;
  i int;
  v int;
  chars constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  out text := '';
BEGIN
  FOR i IN 0..15 LOOP
    v := get_byte(b, i);
    rem := (rem * 256 + v)::bigint % m;
  END LOOP;

  IF rem = 0 THEN
    out := '0';
  ELSE
    WHILE rem > 0 LOOP
      out := substr(chars, (rem % 36)::int + 1, 1) || out;
      rem := rem / 36;
    END LOOP;
  END IF;

  RETURN lpad(upper(out), 8, '0');
END
$$;

-- New trigger function: always set/normalize fish_code to FSH-<8 base36(uuid)>
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

  -- Set if missing OR looks decimal (FSH-<digits>)
  IF code IS NULL OR code ~* '^FSH-\d+$' THEN
    NEW.fish_code := 'FSH-' || public.uuid_to_base36_8(NEW.id);
  END IF;

  RETURN NEW;
END
$$;

-- Rebind the table trigger to the new function
DROP TRIGGER IF EXISTS trg_fish_code_default ON public.fish;
CREATE TRIGGER trg_fish_code_default
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.trg_set_fish_code_from_uuid_base36_8();

COMMIT;
