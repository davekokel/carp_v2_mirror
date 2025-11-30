BEGIN;

ALTER TABLE public.fish_groups
  DROP CONSTRAINT IF EXISTS fish_groups_genotype_code_fk;

ALTER TABLE public.fish_groups
  ADD CONSTRAINT fish_groups_genotype_code_fk
    FOREIGN KEY (genotype_key)
    REFERENCES public.genotypes_v11(genotype_code)
    ON DELETE SET NULL;

COMMIT;
