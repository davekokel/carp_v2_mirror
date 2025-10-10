BEGIN;

-- Rename OUT columns to avoid PL/pgSQL variable name clashes with table columns
DROP FUNCTION IF EXISTS public.ensure_transgene_allele(text, text) CASCADE;

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
  v_digits := (regexp_match(coalesce(p_nickname,''), '(\d+)$'))[1];
  IF v_digits ~ '^\d+$' THEN
    v_num := v_digits::int;
  ELSE
    SELECT COALESCE(MAX(ta.allele_number), 0) + 1
      INTO v_num
      FROM public.transgene_alleles ta
     WHERE ta.transgene_base_code = p_base;
  END IF;

  v_pref := (regexp_match(coalesce(p_nickname,''), '^([A-Za-z]+)'))[1];
  IF v_pref IS NULL OR v_pref = '' THEN
    v_pref := 'allele';
  END IF;

  v_nick := NULLIF(trim(p_nickname), '');
  IF v_nick IS NULL OR v_digits IS NULL THEN
    v_nick := v_pref || v_num::text;
  END IF;

  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (p_base)
  ON CONFLICT DO NOTHING;

  -- No OUT param name matches table column names now, so conflict target is unambiguous
  INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_nickname)
  VALUES (p_base, v_num, v_nick)
  ON CONFLICT (transgene_base_code, allele_number) DO UPDATE
    SET allele_nickname = COALESCE(EXCLUDED.allele_nickname, public.transgene_alleles.allele_nickname)
  RETURNING public.transgene_alleles.allele_number, public.transgene_alleles.allele_nickname
  INTO ret_allele_number, ret_allele_nickname;

  RETURN;
END;
$$;

COMMIT;
