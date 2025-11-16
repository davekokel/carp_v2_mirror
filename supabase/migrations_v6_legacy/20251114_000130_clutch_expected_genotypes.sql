BEGIN;

-- Expected genotype options per clutch_instance.
-- One row = one allele option in the clutch's expected mix.
CREATE TABLE IF NOT EXISTS public.clutch_expected_genotypes (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Link to the clutch this expected genotype belongs to
  clutch_instance_id  uuid NOT NULL
    REFERENCES public.clutch_instances(id)
    ON DELETE CASCADE,

  -- Normalized allele identity (matches transgene_alleles)
  transgene_base_code text   NOT NULL,
  allele_number       integer NOT NULL,

  -- Optional human label (e.g. "pDQM005(gu104)")
  allele_label        text,
  -- Optional origin tag, e.g. 'mom' | 'dad' | 'double'
  source              text,

  created_at          timestamptz NOT NULL DEFAULT now()
);

-- Make it easy to query by clutch
CREATE INDEX IF NOT EXISTS idx_clutch_expected_genotypes_clutch
  ON public.clutch_expected_genotypes (clutch_instance_id);

-- Avoid duplicate allele entries for the same clutch
CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_expected_genotypes_clutch_allele
  ON public.clutch_expected_genotypes (clutch_instance_id, transgene_base_code, allele_number);

COMMIT;
