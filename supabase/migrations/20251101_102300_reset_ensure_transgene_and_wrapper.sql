BEGIN;

-- 0) Ensure helper columns exist
ALTER TABLE public.transgene_alleles
  ADD COLUMN IF NOT EXISTS allele_name text,
  ADD COLUMN IF NOT EXISTS allele_nickname text;

-- 1) Ensure a UNIQUE index on allele_number (name-agnostic; works with ON CONFLICT (col))
CREATE UNIQUE INDEX IF NOT EXISTS ux_transgene_alleles_allele_number
  ON public.transgene_alleles(allele_number);

-- 2) Drop ANY existing versions of ensure_transgene_allele(text,text)
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT oid
    FROM pg_proc
    WHERE pronamespace = 'public'::regnamespace
      AND proname = 'ensure_transgene_allele'
  LOOP
    EXECUTE 'DROP FUNCTION ' || r.oid::regprocedure;
  END LOOP;
END $$;

-- 3) Recreate ensure_transgene_allele using ON CONFLICT (allele_number)
CREATE FUNCTION public.ensure_transgene_allele(
  p_base_code text,
  p_allele_nickname text
)
RETURNS TABLE(out_allele_number int, out_allele_name text)
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

  -- Reuse number for existing (base, nickname)
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

  -- Mint new global number and default names
  v_num  := nextval('public.seq_global_allele_number')::int;
  v_name := 'gu' || v_num;

  INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES (v_base, v_num, v_name, COALESCE(v_nick, v_name))
  ON CONFLICT (allele_number) DO NOTHING;

  RETURN QUERY SELECT v_num, v_name;
END;
$$;

-- 4) Recreate wrapper (uses new OUT names)
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
  v_base text := public._norm_txt(p_base_code);
  v_nick text := public._norm_txt(p_allele_nickname);
  v_num  int;
  v_name text;
  exists_any boolean;
  q text;
BEGIN
  IF p_fish_id IS NULL THEN RETURN QUERY SELECT false,'error','fish_id required'; RETURN; END IF;
  IF v_base   IS NULL THEN RETURN QUERY SELECT false,'skip','no base_code'; RETURN; END IF;

  SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_uuid') INTO has_fish_uuid;
  SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_id')   INTO has_fish_id;
  IF NOT (has_fish_uuid OR has_fish_id) THEN
    RETURN QUERY SELECT false,'error','join_fish_transgene_alleles missing fish_uuid/fish_id';
    RETURN;
  END IF;

  SELECT out_allele_number, out_allele_name INTO v_num, v_name
  FROM public.ensure_transgene_allele(v_base, v_nick);

  IF has_fish_uuid THEN
    q := format('SELECT EXISTS(SELECT 1 FROM public.join_fish_transgene_alleles WHERE fish_uuid=%L AND transgene_base_code=%L AND allele_number=%s)', p_fish_id, v_base, v_num);
  ELSE
    q := format('SELECT EXISTS(SELECT 1 FROM public.join_fish_transgene_alleles WHERE fish_id=%L AND transgene_base_code=%L AND allele_number=%s)', p_fish_id, v_base, v_num);
  END IF;
  EXECUTE q INTO exists_any;
  IF exists_any THEN RETURN QUERY SELECT true,'noop','link already present'; RETURN; END IF;

  IF has_fish_uuid THEN
    q := format('INSERT INTO public.join_fish_transgene_alleles(fish_uuid, transgene_base_code, allele_number) VALUES (%L,%L,%s)', p_fish_id, v_base, v_num);
  ELSE
    q := format('INSERT INTO public.join_fish_transgene_alleles(fish_id, transgene_base_code, allele_number) VALUES (%L,%L,%s)', p_fish_id, v_base, v_num);
  END IF;
  EXECUTE q;

  RETURN QUERY SELECT true,'insert','allele link created';
END;
$$;

COMMIT;
