BEGIN;

-- 1) Drop old FK pointing at genotypes_v11_fish
ALTER TABLE public.fish_instances_v10
  DROP CONSTRAINT IF EXISTS fish_instances_v11_genotype_fk;

-- 2) Add new FK pointing directly at genotypes_v11
ALTER TABLE public.fish_instances_v10
  ADD CONSTRAINT fish_instances_v10_genotype_fk
  FOREIGN KEY (genotype_v11_id)
  REFERENCES public.genotypes_v11(id)
  ON DELETE SET NULL;

-- 3) Replace genotypes_v11_fish with a compatibility VIEW over genotypes_v11

-- Drop table if it still exists (you already copied data across, so nothing is lost)
DROP TABLE IF EXISTS public.genotypes_v11_fish;

CREATE VIEW public.genotypes_v11_fish AS
SELECT
  id,
  genotype_code,
  genotype_pretty,
  genotype_basecodes,
  created_at
FROM public.genotypes_v11;

COMMENT ON VIEW public.genotypes_v11_fish IS
  'Compatibility view: genotypes_v11 is the canonical genotype catalog.';

COMMIT;
