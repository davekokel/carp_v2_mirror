BEGIN;

COMMENT ON COLUMN public.fish_instances_v10.origin_kind IS
  'Construct-based instance kind: background, treated_only, transgenic, or transgenic_and_treated.';

ALTER TABLE public.fish_instances_v10
  ADD COLUMN IF NOT EXISTS source_clutch_id uuid REFERENCES public.clutches(id);

COMMENT ON COLUMN public.fish_instances_v10.source_clutch_id IS
  'Optional FK to the clutch this instance came from (e.g. add clutch to nursery).';

ALTER TABLE public.clutches
  ADD COLUMN IF NOT EXISTS genotype_mix_kind text;

COMMENT ON COLUMN public.clutches.genotype_mix_kind IS
  'Clutch-level genotype mix kind: single_genotype or mixed_genotypes, based on expected offspring genotypes chosen at cross scheduling time.';

COMMIT;
