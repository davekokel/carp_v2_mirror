BEGIN;

-- Add legacy columns if missing (safe/idempotent)
ALTER TABLE public.transgene_allele_registry
ADD COLUMN IF NOT EXISTS base_code text,
ADD COLUMN IF NOT EXISTS legacy_label text;

-- Create the unique index only when both columns exist
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgene_allele_registry'
      AND column_name='base_code'
  )
  AND EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgene_allele_registry'
      AND column_name='legacy_label'
  ) THEN
    CREATE UNIQUE INDEX IF NOT EXISTS uniq_registry_base_legacy
      ON public.transgene_allele_registry (base_code, legacy_label)
      WHERE base_code IS NOT NULL AND legacy_label IS NOT NULL;
  END IF;
END$$;

COMMIT;
