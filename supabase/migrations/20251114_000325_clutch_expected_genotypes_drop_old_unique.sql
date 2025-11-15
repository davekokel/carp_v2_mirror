BEGIN;

-- Drop the legacy uniqueness on (clutch_instance_id, transgene_base_code, allele_number)
-- that prevents the same allele from appearing in multiple patterns.
ALTER TABLE public.clutch_expected_genotypes
  DROP CONSTRAINT IF EXISTS uq_clutch_expected_genotypes_clutch_allele;

-- Ensure the new pattern-aware uniqueness is in place
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.clutch_expected_genotypes'::regclass
      AND conname = 'uq_clutch_expected_genotypes_pattern'
  ) THEN
    ALTER TABLE public.clutch_expected_genotypes
      ADD CONSTRAINT uq_clutch_expected_genotypes_pattern
      UNIQUE (clutch_instance_id, pattern_index, transgene_base_code, allele_number);
  END IF;
END$$;

COMMIT;
