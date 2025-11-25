BEGIN;

-- Ensure the global sequence exists
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

-- Align the sequence with existing max(allele_number), if any.
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

-- Enforce uniqueness constraints for v10
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

CREATE UNIQUE INDEX IF NOT EXISTS uniq_transgene_alleles_nickname_v10
  ON public.transgene_alleles (transgene_base_code, allele_nickname)
  WHERE allele_nickname IS NOT NULL;

COMMIT;
