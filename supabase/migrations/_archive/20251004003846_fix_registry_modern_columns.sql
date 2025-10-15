BEGIN;
DO 28762
BEGIN
  -- 1) Add modern columns if missing and backfill from legacy fields
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public'
      AND table_name='transgene_allele_registry'
      AND column_name='transgene_base_code'
  ) THEN
    ALTER TABLE public.transgene_allele_registry
      ADD COLUMN transgene_base_code text;

    -- If legacy base_code exists, backfill
    IF EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema='public'
        AND table_name='transgene_allele_registry'
        AND column_name='base_code'
    ) THEN
      UPDATE public.transgene_allele_registry
      SET transgene_base_code = base_code
      WHERE transgene_base_code IS NULL AND base_code IS NOT NULL;
    END IF;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgene_allele_registry'
      AND column_name='allele_nickname'
  ) THEN
    ALTER TABLE public.transgene_allele_registry
      ADD COLUMN allele_nickname text;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgene_allele_registry'
      AND column_name='allele_number'
  ) THEN
    ALTER TABLE public.transgene_allele_registry
      ADD COLUMN allele_number integer;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgene_allele_registry'
      AND column_name='created_by'
  ) THEN
    ALTER TABLE public.transgene_allele_registry
      ADD COLUMN created_by text;
  END IF;

  -- 2) Ensure modern unique indexes exist (safe even if legacy ones still exist)
  IF NOT EXISTS (
    SELECT 1 FROM pg_class WHERE relname='uq_tar_base_number' AND relkind='i'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX uq_tar_base_number
             ON public.transgene_allele_registry (transgene_base_code, allele_number)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_class WHERE relname='uq_tar_base_nickname' AND relkind='i'
  ) THEN
    EXECUTE 'CREATE UNIQUE INDEX uq_tar_base_nickname
             ON public.transgene_allele_registry (transgene_base_code, allele_nickname)';
  END IF;
END$$;

COMMIT;
