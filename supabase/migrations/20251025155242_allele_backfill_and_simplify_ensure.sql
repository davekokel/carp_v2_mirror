BEGIN;

-- 1) Backfill any missing allele_name to 'guN'
UPDATE public.transgene_alleles
SET allele_name = 'gu'||allele_number::text
WHERE COALESCE(allele_name,'') = '';

-- (Optional but recommended) enforce not null going forward
ALTER TABLE public.transgene_alleles
  ALTER COLUMN allele_name SET NOT NULL;

-- 2) Replace ensure_allele_from_csv with a simple, reuse-or-insert body
DROP FUNCTION IF EXISTS public.ensure_allele_from_csv(text,text);

CREATE FUNCTION public.ensure_allele_from_csv(
  p_base text,
  p_nick text
)
RETURNS TABLE(allele_number int, allele_name text, allele_nickname text)
LANGUAGE plpgsql
AS $$
DECLARE
  v_base text := trim(p_base);
  v_nick text := nullif(trim(p_nick), '');
  v_num  int;
BEGIN
  -- Ensure base exists (dynamic implementation already present)
  PERFORM public.ensure_transgene_base(v_base);

  -- Reuse existing nickname for this base if present
  SELECT allele_number, allele_name, allele_nickname
    INTO allele_number, allele_name, allele_nickname
  FROM public.transgene_alleles
  WHERE transgene_base_code = v_base
    AND allele_nickname = v_nick
  LIMIT 1;

  IF FOUND THEN
    RETURN NEXT;  -- returns that existing allele
    RETURN;
  END IF;

  -- Otherwise mint next number for this base
  SELECT COALESCE(MAX(allele_number),0) + 1
    INTO v_num
  FROM public.transgene_alleles
  WHERE transgene_base_code = v_base;

  INSERT INTO public.transgene_alleles
    (transgene_base_code, allele_number, allele_name, allele_nickname)
  VALUES
    (v_base, v_num, 'gu'||v_num::text, COALESCE(v_nick, 'gu'||v_num::text))
  ON CONFLICT (transgene_base_code, allele_nickname)
    DO UPDATE SET allele_name = EXCLUDED.allele_name
  RETURNING allele_number, allele_name, allele_nickname
    INTO allele_number, allele_name, allele_nickname;

  RETURN NEXT;
END;
$$;

COMMIT;
