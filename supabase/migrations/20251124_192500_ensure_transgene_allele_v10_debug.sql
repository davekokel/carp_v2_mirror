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
AS $function$
DECLARE
  v_base  text;
  v_nick  text;
  v_row   public.transgene_alleles%ROWTYPE;
  v_name  text;
BEGIN
  v_base := trim(p_base_code);
  RAISE NOTICE '[allocator] called with basecode=%, nickname=%', v_base, p_allele_nickname;

  IF v_base IS NULL OR v_base = '' THEN
    RAISE NOTICE '[allocator] basecode empty, returning';
    RETURN;
  END IF;

  PERFORM 1
  FROM public.transgenes t
  WHERE t.transgene_base_code = v_base;

  IF FOUND THEN
    RAISE NOTICE '[allocator] basecode % FOUND in transgenes', v_base;
  ELSE
    RAISE NOTICE '[allocator] basecode % NOT found in transgenes, checking plasmids', v_base;
    SELECT p.name
    INTO v_name
    FROM public.plasmids p
    WHERE p.code = v_base
    LIMIT 1;

    IF FOUND THEN
      RAISE NOTICE '[allocator] FOUND in plasmids as %; inserting/updating transgenes', v_name;
      INSERT INTO public.transgenes (transgene_base_code, transgene_name, description, created_at)
      VALUES (v_base, v_name, NULL, now())
      ON CONFLICT (transgene_base_code) DO NOTHING;
    ELSE
      RAISE NOTICE '[allocator] basecode % NOT found in plasmids; returning with no rows', v_base;
      RETURN;
    END IF;
  END IF;

  v_nick := trim(p_allele_nickname);
  IF v_nick IS NULL OR v_nick = '' OR lower(v_nick) IN ('nan', 'na', 'none') THEN
    v_nick := NULL;
  END IF;

  IF v_nick IS NOT NULL THEN
    SELECT ta.*
    INTO v_row
    FROM public.transgene_alleles AS ta
    WHERE ta.transgene_base_code = v_base
      AND ta.allele_nickname     = v_nick
    LIMIT 1;

    IF FOUND THEN
      RAISE NOTICE '[allocator] reuse allele for basecode=% nickname=% → allele_number=%',
        v_base, v_nick, v_row.allele_number;
      transgene_base_code := v_row.transgene_base_code;
      allele_number       := v_row.allele_number;
      allele_name         := v_row.allele_name;
      allele_nickname     := v_row.allele_nickname;
      RETURN;
    END IF;
  END IF;

  SELECT nextval('public.transgene_alleles_allele_number_seq')::int
  INTO allele_number;
  allele_name := 'gu' || allele_number;

  IF v_nick IS NULL THEN
    allele_nickname := allele_name;
  ELSE
    allele_nickname := v_nick;
  END IF;

  RAISE NOTICE '[allocator] minting new allele: basecode=% allele_number=% nickname=%',
    v_base, allele_number, allele_nickname;

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
$function$;

COMMIT;
