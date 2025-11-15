BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_clutch_expected_genotypes_clutch_allele'
      AND conrelid = 'public.clutch_expected_genotypes'::regclass
  ) THEN
    ALTER TABLE public.clutch_expected_genotypes
      DROP CONSTRAINT uq_clutch_expected_genotypes_clutch_allele;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'uq_clutch_expected_genotypes_clutch_pattern_allele'
      AND conrelid = 'public.clutch_expected_genotypes'::regclass
  ) THEN
    ALTER TABLE public.clutch_expected_genotypes
      ADD CONSTRAINT uq_clutch_expected_genotypes_clutch_pattern_allele
      UNIQUE (clutch_instance_id, pattern_index, transgene_base_code, allele_number);
  END IF;
END$$;

COMMIT;
