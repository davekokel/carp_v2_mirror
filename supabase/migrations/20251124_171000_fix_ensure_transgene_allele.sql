BEGIN;

CREATE OR REPLACE FUNCTION public.ensure_transgene_allele(
  p_base_code       text,
  p_allele_nickname text
)
RETURNS TABLE (
  transgene_base_code text,
  allele_number       integer,
  allele_name         text,
  allele_nickname     text
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base text;
  v_nick text;
  v_row  public.transgene_alleles%ROWTYPE;
BEGIN
  v_base := trim(p_base_code);
  IF v_base IS NULL OR v_base = '' THEN
    RAISE EXCEPTION 'ensure_transgene_allele: base_code must not be empty';
  END IF;

  v_nick := trim(p_allele_nickname);
  IF v_nick IS NULL OR v_nick = '' OR lower(v_nick) IN ('nan', 'na', 'none') THEN
    v_nick := NULL;
  END IF;

  -- 1) If nickname present, try to reuse existing allele for (base_code, nickname)
  IF v_nick IS NOT NULL THEN
    SELECT ta.*
    INTO v_row
    FROM public.transgene_alleles AS ta
    WHERE ta.transgene_base_code = v_base
      AND ta.allele_nickname     = v_nick
    LIMIT 1;

    IF FOUND THEN
      transgene_base_code := v_row.transgene_base_code;
      allele_number       := v_row.allele_number;
      allele_name         := v_row.allele_name;
      allele_nickname     := v_row.allele_nickname;
      RETURN;
    END IF;
  END IF;

  -- 2) Mint new allele_number from global sequence
  SELECT nextval('public.transgene_alleles_allele_number_seq')::int INTO allele_number;
  allele_name := 'gu' || allele_number;

  IF v_nick IS NULL THEN
    allele_nickname := allele_name;
  ELSE
    allele_nickname := v_nick;
  END IF;

  INSERT INTO public.transgene_alleles (
    transgene_base_code,
    allele_number,
    allele_name,
    allele_nickname,
    created_at
  )
  VALUES (
    v_base,
    allele_number,
    allele_name,
    allele_nickname,
    now()
  );

  transgene_base_code := v_base;
  RETURN;
END;
$$;

COMMIT;
