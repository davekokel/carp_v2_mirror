BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Helper: 8-char base36 from UUID (lower 40 bits), prefixed with FSH-
CREATE OR REPLACE FUNCTION public.uuid_base36_8(u uuid)
RETURNS text
LANGUAGE plpgsql
AS $fn$
DECLARE
  hex text := replace(u::text,'-','');        -- 32 hex chars
  h10 text := right(hex, 10);                 -- lower 40 bits
  n   numeric := 0;
  i   int;
  c   text;
  v   int;
  alphabet constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  out text := '';
BEGIN
  -- hex → numeric accumulator
  FOR i IN 1..length(h10) LOOP
    c := substr(h10, i, 1);
    v := CASE c
           WHEN '0' THEN 0 WHEN '1' THEN 1 WHEN '2' THEN 2 WHEN '3' THEN 3
           WHEN '4' THEN 4 WHEN '5' THEN 5 WHEN '6' THEN 6 WHEN '7' THEN 7
           WHEN '8' THEN 8 WHEN '9' THEN 9
           WHEN 'a' THEN 10 WHEN 'b' THEN 11 WHEN 'c' THEN 12 WHEN 'd' THEN 13
           WHEN 'e' THEN 14 WHEN 'f' THEN 15
           WHEN 'A' THEN 10 WHEN 'B' THEN 11 WHEN 'C' THEN 12 WHEN 'D' THEN 13
           WHEN 'E' THEN 14 WHEN 'F' THEN 15
           ELSE 0
         END;
    n := n*16 + v;
  END LOOP;

  -- numeric → base36 (8 chars, left-padded with zeros)
  FOR i IN 1..8 LOOP
    v := mod(n, 36);
    out := substr(alphabet, v+1, 1) || out;
    n := trunc(n/36);
  END LOOP;

  RETURN 'FSH-' || out;
END
$fn$;

-- 2) Recreate upsert_fish_by_identity to use base36 code
DROP FUNCTION IF EXISTS public.upsert_fish_by_identity(
  text, text, date, text, text, text, text, text, text, text
);

CREATE OR REPLACE FUNCTION public.upsert_fish_by_identity(
  p_seed_batch_id      text,
  p_identity_key       text,
  p_birthday           date,
  p_name_human         text,
  p_genetic_background text,
  p_nickname           text,
  p_in_breeding_stage  text,
  p_description        text,
  p_notes              text,
  p_by                 text
)
RETURNS TABLE (id uuid, fish_code text)
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_hash  text;
  v_found uuid;
BEGIN
  IF p_birthday IS NULL THEN
    RETURN;
  END IF;

  SELECT encode(digest(p_identity_key,'sha256'),'hex') INTO v_hash;

  SELECT f.id INTO v_found
  FROM public.fish f
  WHERE f.identity_hash = v_hash
     OR f.identity_key  = p_identity_key
  LIMIT 1;

  IF v_found IS NOT NULL THEN
    UPDATE public.fish f
       SET birthday           = COALESCE(p_birthday,         f.birthday),
           genetic_background = COALESCE(p_genetic_background, f.genetic_background),
           in_breeding_stage  = COALESCE(p_in_breeding_stage,  f.in_breeding_stage),
           nickname           = COALESCE(p_nickname,          f.nickname),
           description        = COALESCE(p_description,       f.description),
           created_by         = COALESCE(p_by,                f.created_by)
     WHERE f.id = v_found;

    RETURN QUERY SELECT f.id, f.fish_code FROM public.fish f WHERE f.id = v_found;
    RETURN;
  END IF;

  RETURN QUERY
  WITH new_id AS (SELECT gen_random_uuid() AS nid)
  INSERT INTO public.fish(
      id,  fish_code,                       birthday,
      genetic_background, in_breeding_stage, nickname,
      description,     identity_key, identity_hash, created_by, created_at
  )
  SELECT
      n.nid,
      public.uuid_base36_8(n.nid),          -- <-- base36 FSH-XXXXXXXX here
      p_birthday,
      NULLIF(p_genetic_background,''),
      NULLIF(p_in_breeding_stage,''),
      NULLIF(p_nickname,''),
      NULLIF(p_description,''),
      p_identity_key,
      v_hash,
      NULLIF(p_by,''),
      now()
    FROM new_id n
  RETURNING public.fish.id, public.fish.fish_code;
END
$fn$;

COMMIT;
