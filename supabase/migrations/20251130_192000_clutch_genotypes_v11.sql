BEGIN;

-- 1) Preserve old structure for reference
ALTER TABLE public.clutch_expected_genotypes_v11
  RENAME TO clutch_expected_genotypes_v11_legacy;

-- 2) New canonical join table: clutch_genotypes_v11
CREATE TABLE IF NOT EXISTS public.clutch_genotypes_v11 (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_id         uuid NOT NULL
                     REFERENCES public.clutches(id)
                     ON DELETE CASCADE,
  genotype_v11_id   uuid NOT NULL
                     REFERENCES public.genotypes_v11(id)
                     ON DELETE RESTRICT,
  expected_fraction numeric,
  expected_label    text,
  notes             text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  created_by        text
);

-- Avoid duplicate rows for the same clutch/genotype
CREATE UNIQUE INDEX IF NOT EXISTS clutch_genotypes_v11_clutch_genotype_uniq
  ON public.clutch_genotypes_v11 (clutch_id, genotype_v11_id);

COMMENT ON TABLE public.clutch_genotypes_v11 IS
  'v11: join table for expected genotypes per clutch; canonical link from clutches to genotypes_v11.';

COMMIT;
