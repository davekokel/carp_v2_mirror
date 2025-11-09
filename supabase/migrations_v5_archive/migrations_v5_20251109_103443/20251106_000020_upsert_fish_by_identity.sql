BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='seq_fish_code') THEN
    CREATE SEQUENCE public.seq_fish_code;
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.upsert_fish_by_identity(
  p_seed_batch_id  text,
  p_identity_key   text,
  p_dob            date,
  p_name_human     text,
  p_bg             text,
  p_nick           text,
  p_stage          text,
  p_desc           text,
  p_notes          text,
  p_by             text
)
RETURNS TABLE (id uuid, fish_id uuid, fish_code text)
LANGUAGE plpgsql AS $$
DECLARE
  v_key  text;
  v_hash text;
  v_id   uuid;
  v_code text;
BEGIN
  v_key  := COALESCE(p_identity_key,'');
  v_hash := encode(digest(v_key,'sha256'), 'hex');

  SELECT f.id, f.fish_code
    INTO v_id, v_code
  FROM public.fish f
  WHERE f.identity_key = v_key
     OR f.identity_hash = v_hash
  LIMIT 1;

  IF v_id IS NOT NULL THEN
    id := v_id; fish_id := v_id; fish_code := v_code;
    RETURN NEXT; RETURN;
  END IF;

  v_code := 'FSH-'||lpad(nextval('public.seq_fish_code')::text, 8, '0');

  INSERT INTO public.fish (
    id, fish_code, nickname, dob,
    genetic_background, line_building_stage,
    identity_key, identity_hash, created_at
  )
  VALUES (
    gen_random_uuid(),
    v_code,
    NULLIF(p_nick,''),
    p_dob,
    NULLIF(p_bg,''),
    NULLIF(p_stage,''),
    v_key,
    v_hash,
    now()
  )
  RETURNING public.fish.id, public.fish.fish_code INTO v_id, v_code;

  id := v_id; fish_id := v_id; fish_code := v_code;
  RETURN NEXT;
END $$;

COMMIT;
