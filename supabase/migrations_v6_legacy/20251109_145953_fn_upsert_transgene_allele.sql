BEGIN;

-- Recreate helper with the signature your app calls: (text, text) -> (out_base, out_number, out_name)
DROP FUNCTION IF EXISTS public.upsert_transgene_allele(text, text);

CREATE OR REPLACE FUNCTION public.upsert_transgene_allele(
  _base text,
  _allele_name text
)
RETURNS TABLE(out_base text, out_number integer, out_name text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base text := btrim(_base);
  v_name text := NULLIF(btrim(COALESCE(_allele_name,'')),'');
  v_num  integer;
BEGIN
  IF v_base IS NULL OR v_base = '' THEN
    RAISE EXCEPTION 'transgene base code is required';
  END IF;

  -- Ensure base transgene exists
  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (v_base)
  ON CONFLICT (transgene_base_code) DO NOTHING;

  IF v_name IS NOT NULL THEN
    -- If an allele with this name already exists, return it
    SELECT allele_number, allele_name
      INTO v_num, v_name
    FROM public.transgene_alleles
    WHERE transgene_base_code = v_base
      AND lower(COALESCE(allele_name,'')) = lower(v_name)
    LIMIT 1;

    IF v_num IS NULL THEN
      -- Create next available allele number and set name
      SELECT COALESCE(MAX(allele_number),0)+1
        INTO v_num
      FROM public.transgene_alleles
      WHERE transgene_base_code = v_base;

      INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_name)
      VALUES (v_base, v_num, v_name)
      ON CONFLICT (transgene_base_code, allele_number)
      DO UPDATE SET allele_name = COALESCE(public.transgene_alleles.allele_name, EXCLUDED.allele_name);
    END IF;

  ELSE
    -- No name provided: use or create allele #1
    SELECT allele_number, allele_name
      INTO v_num, v_name
    FROM public.transgene_alleles
    WHERE transgene_base_code = v_base
      AND allele_number = 1
    LIMIT 1;

    IF v_num IS NULL THEN
      v_num := 1;
      INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_name)
      VALUES (v_base, v_num, NULL)
      ON CONFLICT DO NOTHING;
    END IF;
  END IF;

  out_base   := v_base;
  out_number := v_num;
  out_name   := v_name;
  RETURN NEXT;
END;
$$;

COMMIT;
