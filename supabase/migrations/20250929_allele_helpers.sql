-- Ensure unique allele per transgene (safe to re-run)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint 
    WHERE conname = 'uq_transgene_allele_per_base'
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT uq_transgene_allele_per_base
      UNIQUE (transgene_base_code, allele_number);
  END IF;
END$$;

-- Helper to generate next numeric allele (as text) per base
CREATE OR REPLACE FUNCTION public.next_allele_number(p_base text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  n int;
BEGIN
  SELECT COALESCE(MAX((allele_number)::int), 0) + 1
    INTO n
  FROM public.transgene_alleles
  WHERE transgene_base_code = p_base
    AND allele_number ~ '^\d+$';
  RETURN n::text;
END
$$;

-- Legacy ↔ core mapping (optional but useful)
CREATE TABLE IF NOT EXISTS public.transgene_allele_legacy_map (
  transgene_base_code   text        NOT NULL,
  allele_number         text        NOT NULL,
  legacy_allele_number  text        NOT NULL,
  created_at            timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (transgene_base_code, legacy_allele_number)
);

-- FK back to core table if not already present
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name='fk_legacy_to_core'
  ) THEN
    ALTER TABLE public.transgene_allele_legacy_map
      ADD CONSTRAINT fk_legacy_to_core
      FOREIGN KEY (transgene_base_code, allele_number)
      REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
      ON DELETE CASCADE;
  END IF;
END$$;

GRANT SELECT ON public.transgene_allele_legacy_map TO anon, authenticated;
