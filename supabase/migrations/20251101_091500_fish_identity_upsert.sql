BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS identity_key        text,
  ADD COLUMN IF NOT EXISTS identity_hash       text,
  ADD COLUMN IF NOT EXISTS dob                 date,
  ADD COLUMN IF NOT EXISTS name_human          text,
  ADD COLUMN IF NOT EXISTS genetic_background  text,
  ADD COLUMN IF NOT EXISTS nickname            text,
  ADD COLUMN IF NOT EXISTS line_building_stage text,
  ADD COLUMN IF NOT EXISTS description         text,
  ADD COLUMN IF NOT EXISTS notes               text,
  ADD COLUMN IF NOT EXISTS created_by          text,
  ADD COLUMN IF NOT EXISTS created_at          timestamptz DEFAULT now();

DO $$
DECLARE
  is_gen boolean;
BEGIN
  SELECT (is_generated = 'ALWAYS') INTO is_gen
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='fish' AND column_name='identity_hash';

  IF NOT coalesce(is_gen,false) THEN
    UPDATE public.fish
    SET identity_hash = encode(digest(coalesce(identity_key,''), 'sha256'), 'hex')
    WHERE identity_key IS NOT NULL
      AND (identity_hash IS NULL OR identity_hash = '');
  END IF;
END$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fish_identity_hash
  ON public.fish(identity_hash)
  WHERE identity_hash IS NOT NULL AND identity_hash <> '';

CREATE OR REPLACE FUNCTION public._norm_txt(p text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT NULLIF(btrim(regexp_replace(coalesce(p,''), '\s+', ' ', 'g')), '')
$$;

CREATE OR REPLACE FUNCTION public.upsert_fish_by_identity(
  p_seed_batch_id text,
  p_identity_key  text,
  p_dob           date,
  p_name_human    text,
  p_bg            text,
  p_nick          text,
  p_stage         text,
  p_desc          text,
  p_notes         text,
  p_by            text
)
RETURNS TABLE(
  ok boolean,
  action text,
  fish_uuid uuid,
  fish_code text,
  msg text
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_key    text := public._norm_txt(p_identity_key);
  v_hash   text := CASE WHEN v_key IS NULL THEN NULL
                        ELSE encode(digest(v_key, 'sha256'), 'hex') END;
  v_id     uuid;
  v_action text;
  is_gen   boolean;
BEGIN
  SELECT (is_generated = 'ALWAYS') INTO is_gen
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='fish' AND column_name='identity_hash';

  IF v_key IS NULL THEN
    RETURN QUERY SELECT false, 'error', NULL::uuid, NULL::text, 'identity_key is required';
    RETURN;
  END IF;

  SELECT f.id INTO v_id
  FROM public.fish f
  WHERE f.identity_hash = v_hash
  LIMIT 1;

  IF v_id IS NULL THEN
    IF coalesce(is_gen,false) THEN
      INSERT INTO public.fish (
        id, identity_key,
        dob, name_human, genetic_background, nickname, line_building_stage,
        description, notes, created_by
      )
      VALUES (
        gen_random_uuid(),
        v_key,
        p_dob,
        public._norm_txt(p_name_human),
        public._norm_txt(p_bg),
        public._norm_txt(p_nick),
        public._norm_txt(p_stage),
        public._norm_txt(p_desc),
        public._norm_txt(p_notes),
        public._norm_txt(p_by)
      )
      RETURNING id INTO v_id;
    ELSE
      INSERT INTO public.fish (
        id, identity_key, identity_hash,
        dob, name_human, genetic_background, nickname, line_building_stage,
        description, notes, created_by
      )
      VALUES (
        gen_random_uuid(),
        v_key,
        v_hash,
        p_dob,
        public._norm_txt(p_name_human),
        public._norm_txt(p_bg),
        public._norm_txt(p_nick),
        public._norm_txt(p_stage),
        public._norm_txt(p_desc),
        public._norm_txt(p_notes),
        public._norm_txt(p_by)
      )
      RETURNING id INTO v_id;
    END IF;
    v_action := 'insert';
  ELSE
    IF coalesce(is_gen,false) THEN
      UPDATE public.fish f SET
        identity_key        = COALESCE(v_key, f.identity_key),
        dob                 = COALESCE(p_dob, f.dob),
        name_human          = COALESCE(public._norm_txt(p_name_human), f.name_human),
        genetic_background  = COALESCE(public._norm_txt(p_bg), f.genetic_background),
        nickname            = COALESCE(public._norm_txt(p_nick), f.nickname),
        line_building_stage = COALESCE(public._norm_txt(p_stage), f.line_building_stage),
        description         = COALESCE(public._norm_txt(p_desc), f.description),
        notes               = COALESCE(public._norm_txt(p_notes), f.notes),
        created_by          = COALESCE(public._norm_txt(p_by), f.created_by)
      WHERE f.id = v_id;
    ELSE
      UPDATE public.fish f SET
        identity_key        = COALESCE(v_key, f.identity_key),
        identity_hash       = COALESCE(v_hash, f.identity_hash),
        dob                 = COALESCE(p_dob, f.dob),
        name_human          = COALESCE(public._norm_txt(p_name_human), f.name_human),
        genetic_background  = COALESCE(public._norm_txt(p_bg), f.genetic_background),
        nickname            = COALESCE(public._norm_txt(p_nick), f.nickname),
        line_building_stage = COALESCE(public._norm_txt(p_stage), f.line_building_stage),
        description         = COALESCE(public._norm_txt(p_desc), f.description),
        notes               = COALESCE(public._norm_txt(p_notes), f.notes),
        created_by          = COALESCE(public._norm_txt(p_by), f.created_by)
      WHERE f.id = v_id;
    END IF;
    v_action := 'update';
  END IF;

  RETURN QUERY
  SELECT true, v_action, f.id, f.fish_code,
         CASE v_action WHEN 'insert' THEN 'fish created' ELSE 'fish updated' END
  FROM public.fish f
  WHERE f.id = v_id;
END;
$$;

COMMIT;