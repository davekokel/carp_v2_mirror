BEGIN;

-- Ensure global sequence for allele_number exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM   pg_class
    WHERE  relkind = 'S'
       AND relname = 'transgene_alleles_allele_number_seq'
  ) THEN
    CREATE SEQUENCE public.transgene_alleles_allele_number_seq;
  END IF;
END $$;

-- Align sequence with existing max allele_number
DO $$
DECLARE
  v_max int;
BEGIN
  SELECT max(allele_number) INTO v_max FROM public.transgene_alleles;
  IF v_max IS NULL THEN
    v_max := 0;
  END IF;
  PERFORM setval('public.transgene_alleles_allele_number_seq', v_max, true);
END $$;

-- Enforce global uniqueness of allele_number
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM   pg_constraint
    WHERE  conrelid = 'public.transgene_alleles'::regclass
       AND conname  = 'transgene_alleles_allele_number_unique'
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT transgene_alleles_allele_number_unique
      UNIQUE (allele_number);
  END IF;
END $$;

-- Enforce per-basecode uniqueness of allele_nickname (when present)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_transgene_alleles_nickname_v10
  ON public.transgene_alleles (transgene_base_code, allele_nickname)
  WHERE allele_nickname IS NOT NULL;

COMMIT;
