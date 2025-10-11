BEGIN;

-- Ensure modern unique key for ON CONFLICT in seed scripts
-- Safe/idempotent: only create if absent
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public'
      AND tablename='transgene_allele_registry'
      AND indexname='uniq_registry_modern_key'
  ) THEN
    CREATE UNIQUE INDEX uniq_registry_modern_key
      ON public.transgene_allele_registry (transgene_base_code, allele_nickname)
      WHERE transgene_base_code IS NOT NULL AND allele_nickname IS NOT NULL;
  END IF;
END$$;

COMMIT;
