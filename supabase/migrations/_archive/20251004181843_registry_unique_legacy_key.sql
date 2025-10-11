BEGIN;

-- Ensure legacy columns exist
ALTER TABLE public.transgene_allele_registry
  ADD COLUMN IF NOT EXISTS base_code text,
  ADD COLUMN IF NOT EXISTS legacy_label text;

-- Dedupe any existing duplicates where both legacy columns are set (keep earliest created_at/id)
WITH d AS (
  SELECT id, base_code, legacy_label,
         row_number() OVER (PARTITION BY base_code, legacy_label ORDER BY created_at NULLS LAST, id) AS rn
  FROM public.transgene_allele_registry
  WHERE base_code IS NOT NULL AND legacy_label IS NOT NULL
)
DELETE FROM public.transgene_allele_registry t
USING d
WHERE t.id = d.id AND d.rn > 1;

-- Drop redundant partial/duplicate indexes (optional cleanup)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND tablename='transgene_allele_registry' AND indexname='uniq_registry_base_legacy') THEN
    DROP INDEX public.uniq_registry_base_legacy;
  END IF;
END$$;

-- Create the canonical UNIQUE (required for ON CONFLICT (base_code, legacy_label))
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.transgene_allele_registry'::regclass
      AND conname='uq_registry_legacy'
  ) THEN
    ALTER TABLE public.transgene_allele_registry
      ADD CONSTRAINT uq_registry_legacy UNIQUE (base_code, legacy_label);
  END IF;
END$$;

COMMIT;
