DROP FUNCTION IF EXISTS public.upsert_transgene_allele(text, text);

CREATE FUNCTION public.upsert_transgene_allele(
  p_base text,
  p_nickname_in text
)
RETURNS TABLE(transgene_base_code text, allele_number int, allele_name text, allele_nickname text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_nickname text := NULLIF(btrim(p_nickname_in), '');
  v_num int;
  v_name text;
  v_base text;
  v_anum int;
  v_aname text;
  v_anick text;
BEGIN
  -- ensure parent base exists (satisfy FK)
  INSERT INTO public.transgenes(transgene_base_code)
  VALUES (p_base)
  ON CONFLICT (transgene_base_code) DO NOTHING;

  -- fast path: nickname present and row exists
  IF v_nickname IS NOT NULL THEN
    SELECT ta.transgene_base_code, ta.allele_number, ta.allele_name, ta.allele_nickname
      INTO v_base, v_anum, v_aname, v_anick
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = p_base
      AND ta.allele_nickname = v_nickname
    LIMIT 1;

    IF v_base IS NOT NULL THEN
      transgene_base_code := v_base;
      allele_number       := v_anum;
      allele_name         := v_aname;
      allele_nickname     := v_anick;
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  -- mint or win race on global allele_number
  LOOP
    BEGIN
      v_num  := nextval('public.transgene_allele_number_seq')::int;
      v_name := 'gu' || v_num::text;

      INSERT INTO public.transgene_alleles(
        transgene_base_code, allele_number, allele_name, allele_nickname
      )
      VALUES (
        p_base, v_num, v_name, COALESCE(v_nickname, v_name)
      )
      RETURNING
        public.transgene_alleles.transgene_base_code,
        public.transgene_alleles.allele_number,
        public.transgene_alleles.allele_name,
        public.transgene_alleles.allele_nickname
      INTO v_base, v_anum, v_aname, v_anick;

      transgene_base_code := v_base;
      allele_number       := v_anum;
      allele_name         := v_aname;
      allele_nickname     := v_anick;
      RETURN NEXT;
      RETURN;

    EXCEPTION
      WHEN unique_violation THEN
        -- another session took that v_num; loop and retry
        CONTINUE;
    END;
  END LOOP;
END
$$;
