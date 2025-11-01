BEGIN;

-- 0) Tanks: add explicit status column with default and check (no generated expr)
ALTER TABLE public.tanks
  ADD COLUMN IF NOT EXISTS status text DEFAULT 'active';
UPDATE public.tanks SET status='active' WHERE status IS NULL;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='ck_tanks_status' AND conrelid='public.tanks'::regclass
  ) THEN
    ALTER TABLE public.tanks
      ADD CONSTRAINT ck_tanks_status CHECK (status IN ('active','to_kill','retired'));
  END IF;
END $$;

-- 1) Ensure global allele sequence and columns
CREATE SEQUENCE IF NOT EXISTS public.seq_global_allele_number START 1;

ALTER TABLE public.transgene_alleles
  ADD COLUMN IF NOT EXISTS allele_name      text,
  ADD COLUMN IF NOT EXISTS allele_nickname  text;

-- Global uniqueness on allele_number
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_transgene_alleles_global_number'
  ) THEN
    CREATE UNIQUE INDEX uq_transgene_alleles_global_number
      ON public.transgene_alleles(allele_number);
  END IF;
END $$;

-- 2) Normalizer (safe if already present)
CREATE OR REPLACE FUNCTION public._norm_txt(p text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$ SELECT NULLIF(btrim(regexp_replace(COALESCE(p,''), '\s+', ' ', 'g')),'') $$;

-- 3) Canonical allele mint/reuse per your rules
DROP FUNCTION IF EXISTS public.ensure_transgene_allele(text, text);
CREATE FUNCTION public.ensure_transgene_allele(
  p_base_code text,
  p_allele_nickname text
)
RETURNS TABLE(allele_number int, allele_name text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base text := public._norm_txt(p_base_code);
  v_nick text := public._norm_txt(p_allele_nickname);
  v_num  int;
  v_name text;
BEGIN
  IF v_base IS NULL THEN
    RAISE EXCEPTION 'base_code required';
  END IF;

  -- If nickname provided and previously used for this base_code, reuse that global number
  IF v_nick IS NOT NULL THEN
    SELECT ta.allele_number, ta.allele_name
    INTO v_num, v_name
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND public._norm_txt(ta.allele_nickname) = v_nick
    LIMIT 1;
    IF v_num IS NOT NULL THEN
      RETURN QUERY SELECT v_num, v_name;
      RETURN;
    END IF;
  END IF;

  -- Otherwise mint a new global number and default allele_name=guN, nickname=CSV or guN
  v_num  := nextval('public.seq_global_allele_number')::int;
  v_name := 'gu' || v_num;

  INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES (v_base, v_num, v_name, COALESCE(v_nick, v_name))
  ON CONFLICT (allele_number) DO NOTHING;

  RETURN QUERY SELECT v_num, v_name;
END;
$$;

-- 4) Replace broken helper with dynamic SQL (no arrays, no malformed literals)
DROP FUNCTION IF EXISTS public.upsert_fish_allele_from_csv(uuid, text, text);
CREATE FUNCTION public.upsert_fish_allele_from_csv(
  p_fish_id   uuid,
  p_base_code text,
  p_allele_nickname text
)
RETURNS TABLE(ok boolean, action text, msg text)
LANGUAGE plpgsql
AS $$
DECLARE
  has_fish_uuid boolean;
  has_fish_id   boolean;
  fish_col      text;

  v_base text := public._norm_txt(p_base_code);
  v_nick text := public._norm_txt(p_allele_nickname);
  v_num  int;
  v_name text;

  exists_any boolean;
  q text;
BEGIN
  IF p_fish_id IS NULL THEN
    RETURN QUERY SELECT false,'error','fish_id required';
    RETURN;
  END IF;
  IF v_base IS NULL THEN
    RETURN QUERY SELECT false,'skip','no base_code';
    RETURN;
  END IF;

  SELECT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_uuid')
  INTO has_fish_uuid;

  SELECT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_id')
  INTO has_fish_id;

  IF NOT (has_fish_uuid OR has_fish_id) THEN
    RETURN QUERY SELECT false,'error','join_fish_transgene_alleles missing fish_uuid/fish_id';
    RETURN;
  END IF;

  -- Get the canonical allele number and name according to your rules
  SELECT allele_number, allele_name
  INTO v_num, v_name
  FROM public.ensure_transgene_allele(v_base, v_nick);

  -- Dedupe link
  IF has_fish_uuid THEN
    q := format(
      'SELECT EXISTS(SELECT 1 FROM public.join_fish_transgene_alleles WHERE fish_uuid=%L AND transgene_base_code=%L AND allele_number=%s)',
      p_fish_id, v_base, v_num
    );
  ELSE
    q := format(
      'SELECT EXISTS(SELECT 1 FROM public.join_fish_transgene_alleles WHERE fish_id=%L AND transgene_base_code=%L AND allele_number=%s)',
      p_fish_id, v_base, v_num
    );
  END IF;
  EXECUTE q INTO exists_any;
  IF exists_any THEN
    RETURN QUERY SELECT true,'noop','link already present';
    RETURN;
  END IF;

  -- Insert link using available fish column
  IF has_fish_uuid THEN
    q := format(
      'INSERT INTO public.join_fish_transgene_alleles(fish_uuid, transgene_base_code, allele_number)
       VALUES (%L, %L, %s)',
      p_fish_id, v_base, v_num
    );
  ELSE
    q := format(
      'INSERT INTO public.join_fish_transgene_alleles(fish_id, transgene_base_code, allele_number)
       VALUES (%L, %L, %s)',
      p_fish_id, v_base, v_num
    );
  END IF;
  EXECUTE q;

  RETURN QUERY SELECT true,'insert','allele link created';
END;
$$;

-- 5) Ensure the "active tank" helper inserts status='active' (idempotent)
DROP FUNCTION IF EXISTS public.ensure_active_tank_for_fish(text);
CREATE FUNCTION public.ensure_active_tank_for_fish(p_fish_code text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v_code text := public._norm_txt(p_fish_code);
  v_fish uuid;
  v_tank_code text;
  has_fish_uuid boolean;
  has_fish_id   boolean;
  has_fish_code boolean;
  has_tank_uuid boolean;
  has_tank_id   boolean;
  has_tank_code boolean;
  fish_col text;
  tank_col text;
  q text;
  exists_any boolean;
BEGIN
  IF v_code IS NULL THEN RAISE EXCEPTION 'fish_code required'; END IF;
  SELECT id INTO v_fish FROM public.fish WHERE fish_code=v_code LIMIT 1;
  IF v_fish IS NULL THEN RAISE EXCEPTION 'fish_code % not found', v_code; END IF;

  v_tank_code := 'TANK('||v_code||')#1';

  -- Ensure tank row with status=active
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tanks' AND column_name='tank_code') THEN
    IF NOT EXISTS (SELECT 1 FROM public.tanks WHERE tank_code=v_tank_code) THEN
      INSERT INTO public.tanks(tank_code,status) VALUES (v_tank_code,'active');
    END IF;
  END IF;

  -- Detect join_fish_tanks shape
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_uuid') INTO has_fish_uuid;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_id')   INTO has_fish_id;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='fish_code') INTO has_fish_code;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='tank_uuid') INTO has_tank_uuid;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='tank_id')   INTO has_tank_id;
  SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_tanks' AND column_name='tank_code') INTO has_tank_code;

  IF has_fish_uuid THEN fish_col:='fish_uuid';
  ELSIF has_fish_id THEN fish_col:='fish_id';
  ELSIF has_fish_code THEN fish_col:='fish_code';
  ELSE RAISE EXCEPTION 'join_fish_tanks needs fish column'; END IF;

  IF has_tank_code THEN tank_col:='tank_code';
  ELSIF has_tank_id THEN tank_col:='tank_id';
  ELSIF has_tank_uuid THEN tank_col:='tank_uuid';
  ELSE RAISE EXCEPTION 'join_fish_tanks needs tank column'; END IF;

  -- Dedupe join row
  IF fish_col IN ('fish_uuid','fish_id') AND tank_col='tank_code' THEN
    q := format('SELECT EXISTS(SELECT 1 FROM public.join_fish_tanks WHERE %I=%L AND tank_code=%L)', fish_col, v_fish, v_tank_code);
  ELSIF fish_col IN ('fish_uuid','fish_id') AND tank_col IN ('tank_id','tank_uuid') THEN
    q := format('SELECT EXISTS(SELECT 1 FROM public.join_fish_tanks WHERE %I=%L AND %I IN (SELECT id FROM public.tanks WHERE tank_code=%L))', fish_col, v_fish, tank_col, v_tank_code);
  ELSIF fish_col='fish_code' AND tank_col='tank_code' THEN
    q := format('SELECT EXISTS(SELECT 1 FROM public.join_fish_tanks WHERE fish_code=%L AND tank_code=%L)', v_code, v_tank_code);
  ELSE
    q := format('SELECT EXISTS(SELECT 1 FROM public.join_fish_tanks WHERE fish_code=%L AND %I IN (SELECT id FROM public.tanks WHERE tank_code=%L))', v_code, tank_col, v_tank_code);
  END IF;
  EXECUTE q INTO exists_any;

  IF NOT exists_any THEN
    IF fish_col='fish_code' AND tank_col='tank_code' THEN
      q := format('INSERT INTO public.join_fish_tanks(fish_code,tank_code) VALUES (%L,%L)', v_code, v_tank_code);
    ELSIF fish_col IN ('fish_uuid','fish_id') AND tank_col='tank_code' THEN
      q := format('INSERT INTO public.join_fish_tanks(%I,tank_code) VALUES (%L,%L)', fish_col, v_fish, v_tank_code);
    ELSIF fish_col IN ('fish_uuid','fish_id') AND tank_col IN ('tank_id','tank_uuid') THEN
      q := format('INSERT INTO public.join_fish_tanks(%I,%I) SELECT %L,id FROM public.tanks WHERE tank_code=%L LIMIT 1', fish_col, tank_col, v_fish, v_tank_code);
    ELSE
      q := format('INSERT INTO public.join_fish_tanks(fish_code,%I) SELECT %L,id FROM public.tanks WHERE tank_code=%L LIMIT 1', tank_col, v_code, v_tank_code);
    END IF;
    EXECUTE q;
  END IF;

  RETURN v_tank_code;
END;
$$;

COMMIT;
