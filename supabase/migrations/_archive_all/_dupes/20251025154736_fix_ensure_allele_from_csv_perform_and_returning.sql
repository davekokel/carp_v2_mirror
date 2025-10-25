BEGIN;

-- Replace ensure_allele_from_csv(text,text) with a PERFORM and qualified RETURNING
DROP FUNCTION IF EXISTS public.ensure_allele_from_csv(text, text);

CREATE FUNCTION public.ensure_allele_from_csv(p_base text, p_allele_nickname text)
RETURNS TABLE(allele_number integer, allele_name text, allele_nickname text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base text := p_base;
  v_nick text := NULLIF(p_allele_nickname, '');
BEGIN
  -- 1) make sure base exists (dynamic col version already installed)
  PERFORM public.ensure_transgene_base(v_base);

  -- 2) insert/reuse allele row, then normalize allele_name = 'gu'||number
  RETURN QUERY
  WITH ins AS (
    INSERT INTO public.transgene_alleles
      (transgene_base_code, allele_number, allele_name, allele_nickname)
    VALUES
      (
        v_base,
        /* pick next number for this base; uniqueness is enforced by uq_transgene_alleles_base_num */
        (SELECT COALESCE(MAX(ta.allele_number), 0) + 1
           FROM public.transgene_alleles ta
          WHERE ta.transgene_base_code = v_base),
        NULL,            -- set in next CTE
        v_nick
      )
    ON CONFLICT ON CONSTRAINT uq_transgene_alleles_base_num
    DO UPDATE SET allele_nickname =
      COALESCE(EXCLUDED.allele_nickname, public.transgene_alleles.allele_nickname)
    RETURNING public.transgene_alleles.transgene_base_code, public.transgene_alleles.allele_number
  ),
  up AS (
    UPDATE public.transgene_alleles t
       SET allele_name = 'gu'||ins.allele_number::text
      FROM ins
     WHERE t.transgene_base_code = ins.transgene_base_code
       AND t.allele_number       = ins.allele_number
    RETURNING t.allele_number, t.allele_name, t.allele_nickname
  )
  SELECT up.allele_number, up.allele_name, up.allele_nickname
    FROM up;
END
$$;

COMMIT;
