BEGIN;

-- 0) Dependencies we rely on (hash) — pgcrypto is already common in your baseline
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Guarded unique index on identity_key (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public'
      AND tablename='fish'
      AND indexname='uq_fish_identity_key'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX uq_fish_identity_key ON public.fish(identity_key)';
  END IF;
END$$;

-- 2) Create/replace helper with the exact signature your app calls
--    upsert_fish_by_identity(
--      _seed_batch_id text, _identity_key text, _dob date, _name_human text,
--      _bg text, _nick text, _stage text, _desc text, _notes text, _by text)
DROP FUNCTION IF EXISTS public.upsert_fish_by_identity(
  text, text, date, text, text, text, text, text, text, text
);

CREATE OR REPLACE FUNCTION public.upsert_fish_by_identity(
  _seed_batch_id text,
  _identity_key  text,
  _dob           date,
  _name_human    text,
  _bg            text,
  _nick          text,
  _stage         text,
  _desc          text,
  _notes         text,
  _by            text
)
RETURNS TABLE(fish_id uuid, inserted boolean)
LANGUAGE plpgsql
AS $$
DECLARE
  v_code text;
BEGIN
  IF _identity_key IS NULL OR btrim(_identity_key)='' THEN
    RAISE EXCEPTION 'identity_key is required';
  END IF;

  -- Generate a deterministic fish_code from identity_key if needed
  -- (F- plus first 12 hex of SHA256(identity_key))
  v_code := 'F-' || substring(encode(digest(_identity_key, 'sha256'), 'hex') for 12);

  RETURN QUERY
  WITH up AS (
    INSERT INTO public.fish(
      fish_code,
      nickname,
      genetic_background,
      in_breeding_stage,
      identity_key,
      birthday
    )
    VALUES (
      v_code,
      NULLIF(btrim(COALESCE(_nick,'')),''),
      NULLIF(btrim(COALESCE(_bg,'')),''),
      NULLIF(btrim(COALESCE(_stage,'')),''),
      _identity_key,
      _dob
    )
    ON CONFLICT (identity_key)
    DO UPDATE SET
      -- converge: only fill missing info; never clobber non-null existing values
      nickname           = COALESCE(EXCLUDED.nickname,           public.fish.nickname),
      genetic_background = COALESCE(EXCLUDED.genetic_background, public.fish.genetic_background),
      in_breeding_stage  = COALESCE(EXCLUDED.in_breeding_stage,  public.fish.in_breeding_stage),
      birthday           = COALESCE(EXCLUDED.birthday,           public.fish.birthday)
    RETURNING id, (xmax = 0) AS inserted_flag
  )
  SELECT id, inserted_flag FROM up;
END;
$$;

COMMIT;
