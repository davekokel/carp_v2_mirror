BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- The failing signature from your error hint:
--   upsert_fish_by_identity(text,text,date,text,text,text,text,text,text,text)
DROP FUNCTION IF EXISTS public.upsert_fish_by_identity(text,text,date,text,text,text,text,text,text,text);

-- Recreate with same arg list, but a stable minimal return rowtype used by your app.
CREATE FUNCTION public.upsert_fish_by_identity(
  p_seed_batch_id  text,
  p_identity_key   text,
  p_bday           date,
  p_name_human     text,
  p_bg             text,
  p_nick           text,
  p_stage          text,
  p_desc           text,
  p_notes          text,
  p_by             text
) RETURNS TABLE(id uuid, fish_code text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_hash text;
  v_row  public.fish%ROWTYPE;
BEGIN
  v_hash := encode(digest(coalesce(p_identity_key,''),'sha256'),'hex');

  -- Try to reuse an existing fish by identity
  SELECT * INTO v_row
  FROM public.fish
  WHERE identity_hash = v_hash OR identity_key = p_identity_key
  LIMIT 1;

  IF FOUND THEN
    id := v_row.id;
    fish_code := v_row.fish_code;
    RETURN NEXT;
    RETURN;
  END IF;

  -- Insert a new fish; assume helper public.uuid_base36_8(uuid) exists in your DB
  WITH new_id AS (SELECT gen_random_uuid() AS id)
  INSERT INTO public.fish
    (id, fish_code, birthday, genetic_background, in_breeding_stage,
     nickname, description, identity_key, identity_hash, created_at)
  SELECT
    nid.id,
    public.uuid_base36_8(nid.id),
    p_bday,
    NULLIF(p_bg,''),
    NULLIF(p_stage,''),
    NULLIF(p_nick,''),
    NULLIF(p_desc,''),
    p_identity_key,
    v_hash,
    now()
  FROM new_id nid
  RETURNING public.fish.id, public.fish.fish_code
  INTO id, fish_code;

  RETURN NEXT;
END;
$$;

COMMIT;
