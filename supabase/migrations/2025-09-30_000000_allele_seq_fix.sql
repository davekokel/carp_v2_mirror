DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE p.proname = 'next_allele_number'
      AND n.nspname = 'public'
      AND pg_get_function_arguments(p.oid) = 'code text'
  ) THEN
    DROP FUNCTION public.next_allele_number(text);
  END IF;
END$$;

CREATE FUNCTION public.next_allele_number(code text)
RETURNS text
LANGUAGE sql
AS $$
  SELECT (COALESCE(MAX(allele_number::int), 0) + 1)::text
  FROM public.transgene_alleles
  WHERE transgene_base_code = next_allele_number.code
$$;

ALTER FUNCTION public.next_allele_number(text) OWNER TO postgres;
