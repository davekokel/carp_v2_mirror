BEGIN;

-- Ensure gen_random_uuid() is available
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) transgenes (parent table for allele base FK)
CREATE TABLE IF NOT EXISTS public.transgenes (
  transgene_base_code text PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text
);

-- 2) fish
CREATE TABLE IF NOT EXISTS public.fish (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_code text UNIQUE,
  name text,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text,
  date_birth date,
  nickname text,
  line_building_stage text
);

-- 3) transgene_alleles (pairs transgene_base_code + allele_number)
CREATE TABLE IF NOT EXISTS public.transgene_alleles (
  transgene_base_code text NOT NULL,
  allele_number int NOT NULL,
  PRIMARY KEY (transgene_base_code, allele_number),
  CONSTRAINT fk_transgene_alleles_base
    FOREIGN KEY (transgene_base_code) REFERENCES public.transgenes(transgene_base_code) ON DELETE CASCADE
);

-- 4) registry (modern + legacy columns)
CREATE TABLE IF NOT EXISTS public.transgene_allele_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  transgene_base_code text NOT NULL,
  allele_number int NOT NULL,
  allele_nickname text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text,
  base_code text,
  legacy_label text
);

-- canonicals the rest of your migrations expect
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

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.transgene_allele_registry'::regclass
      AND conname='uq_registry_legacy'
  ) THEN
    ALTER TABLE public.transgene_allele_registry
      ADD CONSTRAINT uq_registry_legacy UNIQUE (base_code, legacy_label);
  END IF;
END$$;

-- 5) fish_transgene_alleles (links fish to alleles)
CREATE TABLE IF NOT EXISTS public.fish_transgene_alleles (
  fish_id uuid NOT NULL,
  transgene_base_code text NOT NULL,
  allele_number int NOT NULL,
  zygosity text,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by text,
  PRIMARY KEY (fish_id, transgene_base_code, allele_number),
  CONSTRAINT fk_fta_fish FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE,
  CONSTRAINT fk_fta_allele FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number) ON DELETE CASCADE
);

COMMIT;
