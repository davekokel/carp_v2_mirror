-- Ensure shape + constraints
CREATE TABLE IF NOT EXISTS public.transgene_alleles (
  transgene_base_code text NOT NULL,
  allele_number       integer NOT NULL,
  allele_name         text,
  description         text,
  PRIMARY KEY (transgene_base_code, allele_number)
);

-- Fast lookups of names per base (case/trim insensitive)
CREATE UNIQUE INDEX IF NOT EXISTS ux_transgene_alleles_base_name_norm
ON public.transgene_alleles (transgene_base_code, lower(btrim(allele_name)))
WHERE allele_name IS NOT NULL AND btrim(allele_name) <> '';

-- Race-safe allocator: advisory-lock per base, reuse by name if present, else next free int
CREATE OR REPLACE FUNCTION public.upsert_transgene_allele_name(p_base text, p_name text, OUT out_allele_number integer)
LANGUAGE plpgsql AS $$
DECLARE
  base_norm text := btrim(p_base);
  name_norm text := nullif(btrim(p_name), '');
  k bigint := hashtextextended(base_norm, 0);
BEGIN
  IF base_norm IS NULL OR base_norm = '' THEN
    RAISE EXCEPTION 'base code required';
  END IF;

  -- Try to reuse by (base, name)
  IF name_norm IS NOT NULL THEN
    SELECT ta.allele_number
      INTO out_allele_number
    FROM public.transgene_alleles ta
    WHERE ta.transgene_base_code = base_norm
      AND lower(btrim(ta.allele_name)) = lower(name_norm)
    LIMIT 1;

    IF FOUND THEN
      RETURN; -- reuse existing number
    END IF;
  END IF;

  -- Allocate a new number with an advisory lock to avoid races
  PERFORM pg_advisory_xact_lock(k);

  SELECT COALESCE(MAX(allele_number)+1, 1)
    INTO out_allele_number
  FROM public.transgene_alleles
  WHERE transgene_base_code = base_norm;

  INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, allele_name)
  VALUES (base_norm, out_allele_number, name_norm)
  ON CONFLICT (transgene_base_code, allele_number) DO NOTHING;

  RETURN;
END$$;
