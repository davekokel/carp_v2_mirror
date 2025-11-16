BEGIN;

CREATE TABLE IF NOT EXISTS public.legacy_parent_to_allele (
  id                uuid    PRIMARY KEY DEFAULT gen_random_uuid(),
  parent_fish_name  text    NOT NULL,   -- matches zf_female_genotype / zf_male_genotype
  plasmid_base_code text    NOT NULL,
  allele_nickname   text    NOT NULL,

  CONSTRAINT legacy_parent_to_allele_unique
    UNIQUE (parent_fish_name)
);

CREATE INDEX IF NOT EXISTS idx_legacy_parent_to_allele_name
  ON public.legacy_parent_to_allele (parent_fish_name);

COMMIT;
