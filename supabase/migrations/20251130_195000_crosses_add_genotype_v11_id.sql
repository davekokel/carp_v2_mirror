BEGIN;

-- 1) Add canonical FK to genotypes_v11
ALTER TABLE public.crosses
  ADD COLUMN IF NOT EXISTS genotype_v11_id uuid;

-- 2) Rename the old text label so it's clearly legacy
ALTER TABLE public.crosses
  RENAME COLUMN expected_genotype_code TO legacy_expected_genotype_code;

COMMENT ON COLUMN public.crosses.genotype_v11_id IS
  'Canonical v11 expected genotype FK for this cross (genotypes_v11.id).';

COMMENT ON COLUMN public.crosses.legacy_expected_genotype_code IS
  'Legacy text label for expected genotype (e.g. LCL-0001) kept for compatibility.';

COMMIT;
