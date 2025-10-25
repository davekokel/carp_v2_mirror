BEGIN;

-- Keep the existing signature/OUT columns to avoid app breakage.
-- Body is qualified to avoid PL/pgSQL name shadowing; conflict uses the named constraint.
CREATE OR REPLACE FUNCTION public.ensure_allele_from_csv(p_base text, p_nick text)
RETURNS TABLE(allele_number integer, allele_name text, allele_nickname text)
LANGUAGE plpgsql
AS $function$
DECLARE
  v_base text := trim(p_base);
  v_nick text := nullif(trim(p_nick), '');
  v_next int;
BEGIN
  -- Ensure base exists (dynamic version already installed)
  PERFORM public.ensure_transgene_base(v_base);

  -- REUSE: same base + same nickname
  SELECT t.allele_number, t.allele_name, t.allele_nickname
    INTO allele_number, allele_name, allele_nickname
  FROM public.transgene_alleles t
  WHERE t.transgene_base_code = v_base
    AND t.allele_nickname     = v_nick
  LIMIT 1;

  IF FOUND THEN
    RETURN NEXT;
    RETURN;
  END IF;

  -- MINT: next number for this base
  SELECT COALESCE(MAX(t.allele_number), 0) + 1
    INTO v_next
  FROM public.transgene_alleles t
  WHERE t.transgene_base_code = v_base;

  INSERT INTO public.transgene_alleles
    (transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES
    (v_base, v_next, 'gu'||v_next::text, COALESCE(v_nick, 'gu'||v_next::text))
  ON CONFLICT ON CONSTRAINT uq_transgene_alleles_base_num
    DO UPDATE
      SET allele_nickname = COALESCE(EXCLUDED.allele_nickname, public.transgene_alleles.allele_nickname)
  RETURNING
    public.transgene_alleles.allele_number,
    public.transgene_alleles.allele_name,
    public.transgene_alleles.allele_nickname
  INTO allele_number, allele_name, allele_nickname;

  RETURN NEXT;
END;
$function$;

COMMIT;
