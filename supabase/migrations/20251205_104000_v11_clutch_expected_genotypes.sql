BEGIN;

DROP TABLE IF EXISTS public.clutch_expected_genotypes_v11 CASCADE;

CREATE TABLE public.clutch_expected_genotypes_v11 (
    clutch_id     uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,
    genotype_id   uuid NOT NULL REFERENCES public.genotypes_v11(id) ON DELETE CASCADE,
    PRIMARY KEY (clutch_id, genotype_id)
);

COMMENT ON TABLE public.clutch_expected_genotypes_v11 IS
  'v11 expected genotype assignments per clutch, used by v11 forwardfill & mapping scripts';

COMMIT;
