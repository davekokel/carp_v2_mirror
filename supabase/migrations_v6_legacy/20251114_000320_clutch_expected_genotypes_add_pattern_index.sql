BEGIN;

-- 1) Add pattern_index if it doesn't exist yet
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'clutch_expected_genotypes'
      AND column_name  = 'pattern_index'
  ) THEN
    ALTER TABLE public.clutch_expected_genotypes
      ADD COLUMN pattern_index integer;
  END IF;
END$$;

-- 2) Backfill existing rows to pattern_index = 1 where null
UPDATE public.clutch_expected_genotypes
SET pattern_index = 1
WHERE pattern_index IS NULL;

-- 3) Drop any unique/PK constraint that enforces uniqueness on
--    (clutch_instance_id, transgene_base_code, allele_number),
--    because we now want to allow the same allele in multiple patterns.
DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT conname
    FROM pg_constraint
    WHERE conrelid = 'public.clutch_expected_genotypes'::regclass
      AND contype IN ('p','u')
      AND pg_get_constraintdef(oid) LIKE '%(clutch_instance_id, transgene_base_code, allele_number)%'
  LOOP
    EXECUTE format(
      'ALTER TABLE public.clutch_expected_genotypes DROP CONSTRAINT %I',
      r.conname
    );
  END LOOP;
END$$;

-- 4) Add a new unique constraint on (clutch_instance_id, pattern_index, transgene_base_code, allele_number)
ALTER TABLE public.clutch_expected_genotypes
  ADD CONSTRAINT uq_clutch_expected_genotypes_pattern
  UNIQUE (clutch_instance_id, pattern_index, transgene_base_code, allele_number);

COMMIT;
