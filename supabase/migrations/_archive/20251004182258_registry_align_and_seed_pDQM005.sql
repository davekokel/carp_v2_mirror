BEGIN;

-- 1) Add modern columns if missing
ALTER TABLE public.transgene_allele_registry
  ADD COLUMN IF NOT EXISTS transgene_base_code text,
  ADD COLUMN IF NOT EXISTS allele_nickname     text;

-- 2) Backfill modern columns from legacy if they exist but modern is NULL
UPDATE public.transgene_allele_registry
SET transgene_base_code = COALESCE(transgene_base_code, base_code),
    allele_nickname     = COALESCE(allele_nickname,     legacy_label)
WHERE (transgene_base_code IS NULL OR allele_nickname IS NULL)
  AND (base_code IS NOT NULL OR legacy_label IS NOT NULL);

-- 3) Install canonical UNIQUE(modern) required by seeds (idempotent);
DO 28762
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

-- 4) (Optional) keep a legacy unique too, but only as a constraint (not partial);
DO 28762
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

-- 5) Seed canonical mapping for pDQM005:304 (writes both modern+legacy in one row)
INSERT INTO public.transgene_allele_registry
  (transgene_base_code, allele_nickname, allele_number, base_code, legacy_label)
VALUES
  ('pDQM005', '304', 304, 'pDQM005', '304')
ON CONFLICT (transgene_base_code, allele_nickname)
DO UPDATE SET
  allele_number = EXCLUDED.allele_number,
  base_code     = EXCLUDED.base_code,
  legacy_label  = EXCLUDED.legacy_label;

COMMIT;
