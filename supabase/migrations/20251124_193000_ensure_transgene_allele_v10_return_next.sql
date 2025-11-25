BEGIN;

CREATE OR REPLACE FUNCTION public.ensure_transgene_allele(
  p_construct_code    text,
  p_allele_nickname   text
)
RETURNS TABLE(
  transgene_base_code text,
  allele_number       integer,
  allele_name         text,
  allele_nickname     text
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_code text;
  v_nick text;
  v_tg   public.transgenes%ROWTYPE;
  v_al   public.transgene_alleles%ROWTYPE;
  v_num  integer;
  v_name text;
BEGIN
  -- normalize inputs
  v_code := trim(p_construct_code);
  IF v_code IS NULL OR v_code = '' THEN
    RETURN;
  END IF;

  v_nick := trim(p_allele_nickname);
  IF v_nick IS NULL OR lower(v_nick) IN ('', 'nan', 'na', 'none') THEN
    v_nick := NULL;
  END IF;

  -- ensure a transgenes row exists for this canonical code
  SELECT tg.*
  INTO v_tg
  FROM public.transgenes tg
  WHERE tg.transgene_base_code = v_code
  LIMIT 1;

  IF NOT FOUND THEN
    -- try to pull a name from constructs
    SELECT c.construct_name
    INTO v_name
    FROM public.constructs c
    WHERE c.construct_code = v_code
    LIMIT 1;

    INSERT INTO public.transgenes (
      transgene_base_code,
      transgene_name,
      description,
      created_at
    )
    VALUES (
      v_code,
      COALESCE(v_name, v_code),
      NULL,
      now()
    )
    RETURNING * INTO v_tg;
  END IF;

  -- if nickname present, try to reuse existing allele
  IF v_nick IS NOT NULL THEN
    SELECT ta.*
    INTO v_al
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_code
      AND ta.allele_nickname     = v_nick
    LIMIT 1;

    IF FOUND THEN
      transgene_base_code := v_al.transgene_base_code;
      allele_number       := v_al.allele_number;
      allele_name         := v_al.allele_name;
      allele_nickname     := v_al.allele_nickname;

      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  -- otherwise mint a new global allele_number
  SELECT nextval('public.transgene_alleles_allele_number_seq')::int
  INTO v_num;

  v_name := 'gu' || v_num;

  INSERT INTO public.transgene_alleles (
    transgene_base_code,
    allele_number,
    allele_name,
    allele_nickname,
    created_at
  )
  VALUES (
    v_code,
    v_num,
    v_name,
    COALESCE(v_nick, v_name),
    now()
  )
  RETURNING * INTO v_al;

  transgene_base_code := v_al.transgene_base_code;
  allele_number       := v_al.allele_number;
  allele_name         := v_al.allele_name;
  allele_nickname     := v_al.allele_nickname;

  RETURN NEXT;
  RETURN;
END;
$$;

COMMIT;
