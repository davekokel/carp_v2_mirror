BEGIN;

-- Keep these:
--   uq_registry_modern                                     (transgene_base_code, allele_nickname)
--   transgene_allele_registry_transgene_base_code_allele_number_key (transgene_base_code, allele_number)
-- Drop redundant/duplicate uniques on (transgene_base_code, allele_nickname)

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='transgene_allele_registry' AND indexname='uniq_registry_modern_key') THEN
    DROP INDEX public.uniq_registry_modern_key;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='transgene_allele_registry' AND indexname='uq_tar_base_nickname') THEN
    DROP INDEX public.uq_tar_base_nickname;
  END IF;

  -- This name is a constraint-generated index; drop the CONSTRAINT (duplicate of uq_registry_modern)
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.transgene_allele_registry'::regclass
      AND conname='transgene_allele_registry_transgene_base_code_allele_nickna_key'
  ) THEN
    ALTER TABLE public.transgene_allele_registry
      DROP CONSTRAINT transgene_allele_registry_transgene_base_code_allele_nickna_key;
  END IF;
END$$;

-- Ensure the canonical UNIQUE exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.transgene_allele_registry'::regclass
      AND conname='uq_registry_modern'
  ) THEN
    ALTER TABLE public.transgene_allele_registry
      ADD CONSTRAINT uq_registry_modern UNIQUE (transgene_base_code, allele_nickname);
  END IF;
END$$;

COMMIT;
