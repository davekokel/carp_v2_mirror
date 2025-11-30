BEGIN;

ALTER TABLE public.clutch_expected_genotypes_v11
  ADD COLUMN IF NOT EXISTS all_fluor_tag_rollup text;

ALTER TABLE public.clutch_expected_genotypes_v11
  ADD COLUMN IF NOT EXISTS all_organelle_fluor_rollup text;

ALTER TABLE public.clutch_expected_genotypes_v11
  ADD COLUMN IF NOT EXISTS notes text;

ALTER TABLE public.clutch_expected_genotypes_v11
  ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();

ALTER TABLE public.clutch_expected_genotypes_v11
  ADD COLUMN IF NOT EXISTS created_by text DEFAULT current_user;

COMMIT;
