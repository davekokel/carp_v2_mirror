BEGIN;

DROP TABLE IF EXISTS public.treated_clutch_genotypes_v11;

CREATE TABLE public.treated_clutch_genotypes_v11 (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  treated_clutch_id   uuid NOT NULL,
  clutch_genotype_id  uuid NOT NULL,
  is_primary          boolean NOT NULL DEFAULT false,
  created_at          timestamptz NOT NULL DEFAULT now(),
  created_by          text
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_treated_clutch_genotypes_v11_unique
  ON public.treated_clutch_genotypes_v11 (treated_clutch_id, clutch_genotype_id);

COMMENT ON TABLE public.treated_clutch_genotypes_v11 IS
'Treated-clutch-level narrowing of expected offspring genotypes. If a treated clutch has no rows here, it is interpreted as allowing all clutch_genotypes_v11 for its clutch; if rows exist, only those clutch_genotype_id values are considered "in play" for that treated clutch.';

COMMIT;
