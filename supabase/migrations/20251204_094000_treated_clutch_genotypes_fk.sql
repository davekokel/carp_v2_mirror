BEGIN;

-- Connect treated_clutch_genotypes_v11 to the rest of v11 schema.

-- FK: treated_clutch_id → treated_clutches_v11(id)
ALTER TABLE public.treated_clutch_genotypes_v11
  ADD CONSTRAINT fk_treated_clutch_genotypes_treated_clutch
  FOREIGN KEY (treated_clutch_id)
  REFERENCES public.treated_clutches_v11(id)
  ON DELETE CASCADE;

-- FK: clutch_genotype_id → clutch_genotypes_v11(id)
ALTER TABLE public.treated_clutch_genotypes_v11
  ADD CONSTRAINT fk_treated_clutch_genotypes_clutch_genotype
  FOREIGN KEY (clutch_genotype_id)
  REFERENCES public.clutch_genotypes_v11(id)
  ON DELETE CASCADE;

-- Helpful indexes for joins
CREATE INDEX IF NOT EXISTS idx_treated_clutch_genotypes_treated_clutch_id
  ON public.treated_clutch_genotypes_v11(treated_clutch_id);

CREATE INDEX IF NOT EXISTS idx_treated_clutch_genotypes_clutch_genotype_id
  ON public.treated_clutch_genotypes_v11(clutch_genotype_id);

COMMIT;
