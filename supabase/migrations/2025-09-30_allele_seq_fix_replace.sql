-- Replace without dropping (safe if it already exists)
CREATE OR REPLACE FUNCTION public.next_allele_number(code text)
RETURNS text
LANGUAGE sql
AS $$
  SELECT (COALESCE(MAX(allele_number::int), 0) + 1)::text
  FROM public.transgene_alleles
  WHERE transgene_base_code = next_allele_number.code
$$;

ALTER FUNCTION public.next_allele_number(text) OWNER TO postgres;
