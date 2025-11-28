BEGIN;

CREATE TABLE IF NOT EXISTS public.clutch_expected_genotypes_v11 (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_id                   uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,

  -- standard 6 fields (genotype-only here; treatment_code stays NULL for now)
  treatment_code              text,
  genotype_basecode_code      text,
  genotype_transgene_allele_code text,
  treatments_and_transgenes   text,
  all_fluor_tag_rollup        text,
  all_organelle_fluor_rollup  text,

  -- Punnett metadata
  zygocity_vector             text,
  expected_fraction           numeric,
  expected_percent_label      text,

  is_enabled                  boolean NOT NULL DEFAULT true,
  notes                       text,
  created_at                  timestamptz NOT NULL DEFAULT now(),
  created_by                  text
);

CREATE INDEX IF NOT EXISTS clutch_expected_genotypes_v11_clutch_id_idx
  ON public.clutch_expected_genotypes_v11 (clutch_id);

COMMIT;
