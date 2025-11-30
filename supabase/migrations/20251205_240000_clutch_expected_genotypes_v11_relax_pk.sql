BEGIN;

-- Drop the existing primary key (likely on (clutch_id, genotype_id))
ALTER TABLE public.clutch_expected_genotypes_v11
  DROP CONSTRAINT IF EXISTS clutch_expected_genotypes_v11_pkey;

-- Add a surrogate primary key id
ALTER TABLE public.clutch_expected_genotypes_v11
  ADD COLUMN IF NOT EXISTS id uuid PRIMARY KEY DEFAULT gen_random_uuid();

-- Allow genotype_id to be NULL; keep the FK if it exists
ALTER TABLE public.clutch_expected_genotypes_v11
  ALTER COLUMN genotype_id DROP NOT NULL;

COMMIT;
