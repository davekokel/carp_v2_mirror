BEGIN;
DO $$
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
  v_base     text := NULLIF(btrim(p_transgene_base_code), '');
  v_nick_raw text := NULLIF(btrim(p_allele_nickname), '');
  v_nick     text;
  v_num      int;
  v_is_new   boolean := false;
BEGIN
  IF v_base IS NULL THEN
    RAISE EXCEPTION 'ensure_transgene_allele: base code is required';
  END IF;

  IF v_nick_raw IS NOT NULL AND lower(v_nick_raw) IN ('-', 'na', 'n/a', 'none', 'null') THEN
    v_nick_raw := NULL;
  END IF;

  IF v_nick_raw IS NULL THEN
    ret_allele_number := NULL;
    ret_allele_nickname := NULL;
    RETURN NEXT;
    RETURN;
  END IF;

  IF lower(v_nick_raw) IN ('new','new_allele','+') THEN
    v_is_new := true;
  ELSE
    SELECT ta.allele_number, ta.allele_nickname
      INTO v_num, v_nick
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = v_base
      AND lower(ta.allele_nickname) = lower(v_nick_raw)
    LIMIT 1;

    IF FOUND THEN
      ret_allele_number := v_num;
      ret_allele_nickname := v_nick;
      RETURN NEXT;
      RETURN;
    END IF;

    v_is_new := true;
  END IF;

  IF v_is_new THEN
    SELECT COALESCE(MAX(allele_number), 0) + 1
      INTO v_num
    FROM public.transgene_alleles
    WHERE transgene_base_code = v_base;

    INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_nickname)
    VALUES (
      v_base,
      v_num,
      CASE
        WHEN lower(v_nick_raw) IN ('new','new_allele','+') THEN v_num::text
        ELSE v_nick_raw
      END
    )
    RETURNING allele_number, allele_nickname
    INTO ret_allele_number, ret_allele_nickname;

    RETURN NEXT;
    RETURN;
  END IF;

  ret_allele_number := NULL;
  ret_allele_nickname := NULL;
  RETURN NEXT;
  RETURN;
END;
$$;

COMMIT;
