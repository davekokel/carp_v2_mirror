BEGIN;
DO 28762
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_ta_base_nick_ci'
  ) THEN
    CREATE UNIQUE INDEX uq_ta_base_nick_ci
      ON public.transgene_alleles (transgene_base_code, lower(allele_nickname))
      WHERE allele_nickname IS NOT NULL;
  END IF;
END$$;

UPDATE public.transgene_alleles
SET allele_number = NULL
WHERE allele_number = 0;

CREATE OR REPLACE FUNCTION public.ensure_transgene_allele(
  p_transgene_base_code text,
  p_allele_nickname     text DEFAULT NULL
)
RETURNS TABLE (ret_allele_number int, ret_allele_nickname text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base  text := NULLIF(btrim(p_transgene_base_code), '');
  v_nick  text := NULLIF(btrim(p_allele_nickname), '');
  v_is_new boolean := false;
BEGIN
  IF v_base IS NULL THEN
    RAISE EXCEPTION 'ensure_transgene_allele: base code is required';
  END IF;

  IF v_nick IS NOT NULL AND lower(v_nick) IN ('-', 'na', 'n/a', 'none', 'null') THEN
    v_nick := NULL;
  END IF;

  IF v_nick IS NOT NULL AND lower(v_nick) IN ('new', 'new_allele', '+') THEN
    v_is_new := true;
  END IF;

  IF v_nick IS NOT NULL AND NOT v_is_new THEN
    SELECT ta.allele_number, ta.allele_nickname
      INTO ret_allele_number, ret_allele_nickname
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(ta.allele_nickname) = lower(v_nick)
    LIMIT 1;

    IF FOUND THEN
      RETURN;
    ELSE
      v_is_new := true;
    END IF;
  END IF;

  IF v_is_new THEN
    WITH next_num AS (
      SELECT COALESCE(MAX(allele_number), 0) + 1 AS n
      FROM public.transgene_alleles
      WHERE transgene_base_code = v_base
    ), ins AS (
      INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_nickname)
      SELECT v_base, n, v_nick FROM next_num
      RETURNING allele_number, allele_nickname
    )
    SELECT allele_number, allele_nickname
      INTO ret_allele_number, ret_allele_nickname
    FROM ins;
    RETURN;
  END IF;

  ret_allele_number := NULL;
  ret_allele_nickname := NULL;
  RETURN;
END;
$$;

COMMIT;
