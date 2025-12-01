BEGIN;

-- v11: treated_clutches_v11
CREATE TABLE IF NOT EXISTS public.treated_clutches_v11 (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_id         uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,
  treated_clutch_code text NOT NULL,
  treatment_id      uuid NOT NULL REFERENCES public.treatments(id) ON DELETE RESTRICT,
  n_embryos         integer,
  notes             text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  created_by        text NOT NULL DEFAULT 'system',
  UNIQUE (treated_clutch_code)
);

-- v11: join_genotype_constructs_v11
CREATE TABLE IF NOT EXISTS public.join_genotype_constructs_v11 (
  genotype_id uuid NOT NULL REFERENCES public.genotypes_v11(id) ON DELETE CASCADE,
  construct_id uuid NOT NULL REFERENCES public.constructs(id) ON DELETE CASCADE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (genotype_id, construct_id)
);

COMMIT;
