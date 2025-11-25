BEGIN;

-- Ensure the sequence exists
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

-- Safely align the sequence with existing max(allele_number), if any.
DO $$
DECLARE
  v_max int;
BEGIN
  SELECT max(allele_number) INTO v_max
  FROM public.transgene_alleles;

  IF v_max IS NULL OR v_max < 1 THEN
    PERFORM setval('public.transgene_alleles_allele_number_seq', 1, false);
  ELSE
    PERFORM setval('public.transgene_alleles_allele_number_seq', v_max, true);
  END IF;
END $$;

COMMIT;
