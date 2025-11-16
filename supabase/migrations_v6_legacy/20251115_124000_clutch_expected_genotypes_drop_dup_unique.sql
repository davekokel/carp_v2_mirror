BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_clutch_expected_genotypes_pattern'
      AND conrelid = 'public.clutch_expected_genotypes'::regclass
  ) THEN
    ALTER TABLE public.clutch_expected_genotypes
      DROP CONSTRAINT uq_clutch_expected_genotypes_pattern;
  END IF;
END$$;

COMMIT;
