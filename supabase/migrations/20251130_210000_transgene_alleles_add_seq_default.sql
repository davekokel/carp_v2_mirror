BEGIN;

-- 1) Create a global sequence for allele_number if it does not exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'S'
      AND c.relname = 'transgene_alleles_allele_number_seq'
      AND n.nspname = 'public'
  ) THEN
    CREATE SEQUENCE public.transgene_alleles_allele_number_seq
      AS integer
      START WITH 1
      INCREMENT BY 1
      NO MINVALUE
      NO MAXVALUE
      CACHE 1;
  END IF;
END $$;

-- 2) If there are existing rows, advance the sequence past the current max allele_number.
--    On a fresh DB, transgene_alleles will be empty; in that case, do nothing and keep the default start at 1.
DO $$
DECLARE
  v_max integer;
BEGIN
  SELECT MAX(allele_number) INTO v_max
  FROM public.transgene_alleles;

  IF v_max IS NULL OR v_max < 1 THEN
    -- No rows yet; leave sequence at default start (1).
    RETURN;
  ELSE
    -- Set the sequence so that nextval() will give v_max + 1.
    PERFORM setval('public.transgene_alleles_allele_number_seq', v_max, true);
  END IF;
END $$;

-- 3) Set a DEFAULT on allele_number so callers can use nextval() implicitly if desired
ALTER TABLE public.transgene_alleles
  ALTER COLUMN allele_number DROP DEFAULT;

ALTER TABLE public.transgene_alleles
  ALTER COLUMN allele_number SET DEFAULT nextval('public.transgene_alleles_allele_number_seq');

COMMENT ON SEQUENCE public.transgene_alleles_allele_number_seq IS
  'Global sequence for transgene_alleles.allele_number (guN)';

COMMENT ON COLUMN public.transgene_alleles.allele_number IS
  'Global canonical allele integer (guN), assigned via transgene_alleles_allele_number_seq.';

COMMIT;
