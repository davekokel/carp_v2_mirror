BEGIN;

-- 1) Add genotype_v11_id to fish_lines
ALTER TABLE public.fish_lines
  ADD COLUMN IF NOT EXISTS genotype_v11_id uuid;

-- 2) Backfill from fish_groups.genotype_key → genotypes_v11.genotype_code
UPDATE public.fish_lines fl
SET genotype_v11_id = g.id
FROM public.fish_groups fg
JOIN public.genotypes_v11 g
  ON g.genotype_code = fg.genotype_key
WHERE fl.fish_group_id = fg.id
  AND fl.genotype_v11_id IS NULL;

-- 3) Add FK (now that values are populated)
ALTER TABLE public.fish_lines
  ADD CONSTRAINT fk_fish_lines_genotype_v11
  FOREIGN KEY (genotype_v11_id)
  REFERENCES public.genotypes_v11(id)
  ON DELETE RESTRICT;

-- Useful index for joins
CREATE INDEX IF NOT EXISTS idx_fish_lines_genotype_v11_id
  ON public.fish_lines(genotype_v11_id);

COMMIT;
