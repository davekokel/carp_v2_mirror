BEGIN;

-- 1) truncate treatments if present
DO $$
BEGIN
  IF to_regclass('public.injected_plasmid_treatments') IS NOT NULL THEN
    TRUNCATE TABLE public.injected_plasmid_treatments RESTART IDENTITY;
  END IF;
  IF to_regclass('public.injected_rna_treatments') IS NOT NULL THEN
    TRUNCATE TABLE public.injected_rna_treatments RESTART IDENTITY;
  END IF;
END$$;

-- 2) truncate links & fish (guarded)
DO $$
BEGIN
  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN
    TRUNCATE TABLE public.fish_transgene_alleles RESTART IDENTITY;
  END IF;
  IF to_regclass('public.fish') IS NOT NULL THEN
    TRUNCATE TABLE public.fish RESTART IDENTITY CASCADE;
  END IF;
END$$;

-- 3) truncate allocator registry & per-base counters (guarded)
DO $$
BEGIN
  IF to_regclass('public.transgene_allele_registry') IS NOT NULL THEN
    TRUNCATE TABLE public.transgene_allele_registry RESTART IDENTITY;
  END IF;
  IF to_regclass('public.transgene_allele_counters') IS NOT NULL THEN
    TRUNCATE TABLE public.transgene_allele_counters RESTART IDENTITY;
  END IF;
  IF to_regclass('public.transgene_alleles') IS NOT NULL THEN
    TRUNCATE TABLE public.transgene_alleles RESTART IDENTITY;
  END IF;
END$$;

-- 4) recreate allocator tables if missing (idempotent)
DO $$
BEGIN
  IF to_regclass('public.transgene_allele_registry') IS NULL THEN
    CREATE TABLE public.transgene_allele_registry(
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      transgene_base_code text NOT NULL,
      allele_number integer NOT NULL,
      allele_nickname text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      created_by text NULL
    );
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='uq_tar_base_number' AND relkind='i') THEN
    CREATE UNIQUE INDEX uq_tar_base_number
      ON public.transgene_allele_registry (transgene_base_code, allele_number);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='uq_tar_base_nickname' AND relkind='i') THEN
    CREATE UNIQUE INDEX uq_tar_base_nickname
      ON public.transgene_allele_registry (transgene_base_code, allele_nickname);
  END IF;

  IF to_regclass('public.transgene_allele_counters') IS NULL THEN
    CREATE TABLE public.transgene_allele_counters(
      transgene_base_code text PRIMARY KEY,
      next_number integer NOT NULL DEFAULT 1
    );
  END IF;
END$$;

COMMIT;
