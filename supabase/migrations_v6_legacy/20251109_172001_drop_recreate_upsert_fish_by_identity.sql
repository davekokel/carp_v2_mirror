BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- drop the old signature so we can change OUT parameters safely
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

  SELECT id INTO v_found
    FROM public.fish
   WHERE identity_hash = v_hash
      OR identity_key  = p_identity_key
   LIMIT 1;

  IF v_found IS NOT NULL THEN
    UPDATE public.fish
       SET birthday           = COALESCE(p_birthday,        birthday),
           genetic_background = COALESCE(p_genetic_background, genetic_background),
           in_breeding_stage  = COALESCE(p_in_breeding_stage,  in_breeding_stage),
           nickname           = COALESCE(p_nickname,         nickname),
           description        = COALESCE(p_description,      description),
           created_by         = COALESCE(p_by,               created_by)
     WHERE id = v_found;

    RETURN QUERY SELECT id, fish_code FROM public.fish WHERE id = v_found;
    RETURN;
  END IF;

  RETURN QUERY
  WITH new_id AS (SELECT gen_random_uuid() AS id)
  INSERT INTO public.fish(
      id,  fish_code,                         birthday,
      genetic_background, in_breeding_stage,  nickname,
      description,     identity_key, identity_hash, created_by, created_at
  )
  SELECT
      n.id,
      'F-' || replace(n.id::text,'-',''),
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
  RETURNING id, fish_code;
END
$fn$;

COMMIT;
