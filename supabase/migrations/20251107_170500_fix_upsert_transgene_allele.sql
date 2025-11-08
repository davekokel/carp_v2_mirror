BEGIN;

CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(
  p_transgene_base_code text,
  p_allele_nickname text
)
RETURNS TABLE(transgene_base_code text, allele_number integer) AS $$
DECLARE
  v_transgene_base_code text := trim(p_transgene_base_code);
  v_nick text := nullif(trim(p_allele_nickname), '');
  v_allele_number integer;
BEGIN
  IF v_transgene_base_code IS NULL OR v_transgene_base_code = '' THEN
    RAISE NOTICE 'No transgene base code provided.';
    RETURN;
  END IF;

  -- ensure transgene exists
  INSERT INTO public.transgenes (transgene_base_code, transgene_name)
  VALUES (v_transgene_base_code, v_transgene_base_code)
  ON CONFLICT (transgene_base_code) DO NOTHING;

  -- try to find existing allele with same nickname for this transgene
  SELECT allele_number INTO v_allele_number
  FROM public.transgene_alleles
  WHERE transgene_base_code = v_transgene_base_code
    AND (v_nick IS NOT NULL AND allele_nickname = v_nick)
  LIMIT 1;

  -- otherwise mint new global allele number
  IF v_allele_number IS NULL THEN
    SELECT COALESCE(MAX(allele_number), 0) + 1 INTO v_allele_number FROM public.transgene_alleles;
    INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name, allele_nickname)
    VALUES (
      v_transgene_base_code,
      v_allele_number,
      'gu' || v_allele_number::text,
      COALESCE(v_nick, 'gu' || v_allele_number::text)
    )
    ON CONFLICT DO NOTHING;
  END IF;

  RETURN QUERY
  SELECT v_transgene_base_code, v_allele_number;
END;
$$ LANGUAGE plpgsql;

COMMIT;
