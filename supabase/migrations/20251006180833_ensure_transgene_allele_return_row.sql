BEGIN;

-- Recreate with non-ambiguous OUT names, and explicitly EMIT one row
CREATE OR REPLACE FUNCTION public.ensure_transgene_allele(
  p_base text,
  p_nickname text
) RETURNS TABLE(ret_allele_number int, ret_allele_nickname text)
LANGUAGE plpgsql AS $$
DECLARE
  v_digits   text;
  v_num      int;
  v_pref     text;
  v_nick     text;
BEGIN
  -- Extract trailing digits from nickname (if any)
  v_digits := (regexp_match(coalesce(p_nickname,''), '(\d+)$'))[1];

  -- Honor explicit number in nickname, else allocate next
  IF v_digits ~ '^\d+$' THEN
    v_num := v_digits::int;
  ELSE
    SELECT COALESCE(MAX(ta.allele_number), 0) + 1
      INTO v_num
      FROM public.transgene_alleles ta
     WHERE ta.transgene_base_code = p_base;
  END IF;

  -- Build a nickname if one isn't provided; default prefix 'allele'
  v_pref := (regexp_match(coalesce(p_nickname,''), '^([A-Za-z]+)'))[1];
  IF v_pref IS NULL OR v_pref = '' THEN
    v_pref := 'allele';
  END IF;

  v_nick := NULLIF(trim(p_nickname), '');
  IF v_nick IS NULL OR v_digits IS NULL THEN
    v_nick := v_pref || v_num::text;
  END IF;

  -- Ensure base exists
  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (p_base)
  ON CONFLICT DO NOTHING;

  -- Upsert allele row and capture the actual number/nickname returned by the table
  INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_nickname)
  VALUES (p_base, v_num, v_nick)
  ON CONFLICT (transgene_base_code, allele_number) DO UPDATE
    SET allele_nickname = COALESCE(EXCLUDED.allele_nickname, public.transgene_alleles.allele_nickname)
  RETURNING allele_number, allele_nickname
  INTO ret_allele_number, ret_allele_nickname;

  -- EXPLICITLY emit a row (this is what the importer expects)
  RETURN QUERY SELECT ret_allele_number, ret_allele_nickname;
END;
$$;

COMMIT;
