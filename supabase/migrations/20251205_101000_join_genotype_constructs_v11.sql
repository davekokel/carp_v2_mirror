BEGIN;

DROP TABLE IF EXISTS public.join_genotype_constructs_v11 CASCADE;

CREATE TABLE public.join_genotype_constructs_v11 (
    genotype_id  uuid NOT NULL REFERENCES public.genotypes_v11(id) ON DELETE CASCADE,
    construct_id uuid NOT NULL REFERENCES public.constructs(id) ON DELETE CASCADE,
    PRIMARY KEY (genotype_id, construct_id)
);

COMMENT ON TABLE public.join_genotype_constructs_v11 IS
  'v11 mapping of genotype → construct via normalized constructs table.';

COMMIT;
