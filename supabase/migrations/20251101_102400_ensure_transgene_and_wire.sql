BEGIN;

CREATE OR REPLACE FUNCTION public._norm_txt(p text)
RETURNS text
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$ SELECT NULLIF(btrim(regexp_replace(coalesce(p,''), '\s+', ' ', 'g')),'') $$;

CREATE OR REPLACE FUNCTION public.ensure_transgene(p_base_code text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  v_base text := public._norm_txt(p_base_code);
BEGIN
  IF v_base IS NULL THEN
    RAISE EXCEPTION 'base_code required';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.transgenes WHERE transgene_base_code = v_base) THEN
    INSERT INTO public.transgenes(transgene_base_code) VALUES (v_base);
  END IF;
  RETURN v_base;
END;
$$;

CREATE OR REPLACE FUNCTION public.ensure_transgene_allele(
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
  v_base := public.ensure_transgene(v_base);

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

  v_num  := nextval('public.seq_global_allele_number')::int;
  v_name := 'gu' || v_num;

  INSERT INTO public.transgene_alleles(transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES (v_base, v_num, v_name, COALESCE(v_nick, v_name))
  ON CONFLICT (allele_number) DO NOTHING;

  RETURN QUERY SELECT v_num, v_name;
END;
$$;

COMMIT;
