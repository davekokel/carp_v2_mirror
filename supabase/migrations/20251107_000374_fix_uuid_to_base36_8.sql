BEGIN;

-- Make sure gen_random_uuid() exists if we ever need it in the trigger
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Replace helper: compute (UUID mod 36^8) with byte-wise modulo, then encode base36 (8 chars)
CREATE OR REPLACE FUNCTION public.uuid_to_base36_8(p uuid)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  b bytea := decode(replace(p::text, '-', ''), 'hex');  -- 16 bytes
  m bigint := 36^8;                                     -- 2,821,109,907,456 (fits in bigint)
  rem bigint := 0;
  i int;
  v int;
  chars constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  out text := '';
BEGIN
  -- modulo reduction over 16 bytes: rem = (rem*256 + byte) % m
  FOR i IN 0..15 LOOP
    v := get_byte(b, i);
    rem := (rem * 256 + v)::bigint % m;
  END LOOP;

  -- convert remainder to base36
  IF rem = 0 THEN
    out := '0';
  ELSE
    WHILE rem > 0 LOOP
      out := substr(chars, (rem % 36)::int + 1, 1) || out;
      rem := rem / 36;
    END LOOP;
  END IF;

  -- fixed width 8, uppercase
  RETURN lpad(upper(out), 8, '0');
END
$$;

-- The trigger & name from the previous migration remain valid; no need to recreate.
-- Just backfill any rows still decimal or blank now that the helper is fixed.
UPDATE public.fish f
SET fish_code = 'FSH-' || public.uuid_to_base36_8(f.id)
WHERE (fish_code IS NULL OR fish_code ~* '^FSH-\d+$');

COMMIT;
