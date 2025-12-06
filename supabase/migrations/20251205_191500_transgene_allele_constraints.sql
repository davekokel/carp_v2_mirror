BEGIN;

-- Ensure global allele_number sequence exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_class
    WHERE relkind = 'S'
      AND relname = 'transgene_alleles_allele_number_seq'
  ) THEN
    CREATE SEQUENCE public.transgene_alleles_allele_number_seq;
  END IF;
END$$;

-- Add UNIQUE(allele_number) if missing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'transgene_alleles_allele_number_key'
      AND conrelid = 'public.transgene_alleles'::regclass
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT transgene_alleles_allele_number_key
        UNIQUE (allele_number);
  END IF;
END$$;

-- Add UNIQUE(transgene_base_code, allele_nickname) if missing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'transgene_alleles_base_nickname_key'
      AND conrelid = 'public.transgene_alleles'::regclass
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT transgene_alleles_base_nickname_key
        UNIQUE (transgene_base_code, allele_nickname);
  END IF;
END$$;

COMMIT;
