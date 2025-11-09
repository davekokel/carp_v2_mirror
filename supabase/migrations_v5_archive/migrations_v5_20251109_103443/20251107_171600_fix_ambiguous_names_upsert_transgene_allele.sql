BEGIN;

-- replace the function with non-conflicting OUT names and ON CONSTRAINT usage
DROP FUNCTION IF EXISTS public.upsert_transgene_allele(text, text);

CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(
  p_transgene_base_code text,
  p_allele_nickname     text
)
RETURNS TABLE (
  out_base   text,
  out_number bigint,
  out_name   text
) AS $$
DECLARE
  v_base text := btrim(p_transgene_base_code);
  v_nick text := NULLIF(btrim(p_allele_nickname), '');
  v_num  bigint;
  v_name text;
BEGIN
  IF v_base IS NULL OR v_base = '' THEN
    RETURN;
  END IF;

  -- ensure a transgene row exists (only base column)
  INSERT INTO public.transgenes (transgene_base_code)
  VALUES (v_base)
  ON CONFLICT ON CONSTRAINT transgenes_pkey DO NOTHING;

  -- try reuse by nickname (within same base), case-insensitive
  IF v_nick IS NOT NULL THEN
    SELECT ta.allele_number, ta.allele_name
      INTO v_num, v_name
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(btrim(ta.allele_nickname)) = lower(btrim(v_nick))
    LIMIT 1;

    IF v_num IS NOT NULL THEN
      out_base := v_base; out_number := v_num; out_name := v_name;
      RETURN NEXT; RETURN;
    END IF;
  END IF;

  -- mint new global number (prefer sequence; fallback to MAX+1)
  BEGIN
    v_num := nextval('public.seq_global_allele_number');
  EXCEPTION
    WHEN undefined_table OR undefined_object THEN
      SELECT COALESCE(MAX(allele_number), 0) + 1 INTO v_num FROM public.transgene_alleles;
  END;

  v_name := 'gu' || v_num::text;

  INSERT INTO public.transgene_alleles (
    transgene_base_code, allele_number, allele_name, allele_nickname
  ) VALUES (
    v_base, v_num, v_name, COALESCE(v_nick, v_name)
  )
  ON CONFLICT ON CONSTRAINT transgene_alleles_pkey DO NOTHING;

  out_base := v_base; out_number := v_num; out_name := v_name;
  RETURN NEXT;
END
$$ LANGUAGE plpgsql;

COMMIT;
