BEGIN;

CREATE TABLE IF NOT EXISTS public.clutch_parent_genotypes_v11 (
  clutch_id       uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,
  parent_role     text NOT NULL CHECK (parent_role IN ('female','male')),
  genotype_v11_id uuid NOT NULL REFERENCES public.genotypes_v11(id),
  PRIMARY KEY (clutch_id, parent_role)
);

COMMENT ON TABLE public.clutch_parent_genotypes_v11 IS
'Links each clutch to female/male parent genotypes in v11.';

COMMIT;
