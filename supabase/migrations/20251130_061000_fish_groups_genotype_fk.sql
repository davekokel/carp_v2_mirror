BEGIN;

-- Link fish_groups.genotype_key to genotypes_v11.genotype_code
ALTER TABLE public.fish_groups
ADD CONSTRAINT fish_groups_genotype_code_fk
FOREIGN KEY (genotype_key)
REFERENCES public.genotypes_v11(genotype_code);

COMMIT;
