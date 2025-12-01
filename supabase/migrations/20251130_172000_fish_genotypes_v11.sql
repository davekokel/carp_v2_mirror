BEGIN;

CREATE TABLE IF NOT EXISTS public.fish_genotypes_v11 (
  fish_id     uuid NOT NULL REFERENCES public.fish_instances_v10(id) ON DELETE CASCADE,
  genotype_id uuid NOT NULL REFERENCES public.genotypes_v11(id)      ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (fish_id, genotype_id)
);

COMMIT;
