BEGIN;

CREATE TABLE IF NOT EXISTS public.genotypes (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  genotype_code      text UNIQUE NOT NULL,
  genotype_name      text,
  genetic_background text,
  source_system      text NOT NULL DEFAULT 'core',
  notes              text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_genotype_transgene_alleles (
  genotype_id         uuid NOT NULL,
  transgene_base_code text NOT NULL,
  allele_number       integer NOT NULL,
  zygosity            text,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_join_genotype_transgene_alleles
    PRIMARY KEY (genotype_id, transgene_base_code, allele_number),
  CONSTRAINT fk_jgta_genotype
    FOREIGN KEY (genotype_id)
    REFERENCES public.genotypes(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_jgta_transgene_allele
    FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_jgta_genotype_id
  ON public.join_genotype_transgene_alleles (genotype_id);

CREATE INDEX IF NOT EXISTS idx_jgta_transgene
  ON public.join_genotype_transgene_alleles (transgene_base_code, allele_number);

CREATE TABLE IF NOT EXISTS public.join_fish_genotypes (
  fish_id      uuid NOT NULL,
  genotype_id  uuid NOT NULL,
  confidence   text,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_join_fish_genotypes
    PRIMARY KEY (fish_id, genotype_id),
  CONSTRAINT fk_jfg_fish
    FOREIGN KEY (fish_id)
    REFERENCES public.fish_instance(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_jfg_genotype
    FOREIGN KEY (genotype_id)
    REFERENCES public.genotypes(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jfg_fish_id
  ON public.join_fish_genotypes (fish_id);

CREATE INDEX IF NOT EXISTS idx_jfg_genotype_id
  ON public.join_fish_genotypes (genotype_id);

COMMIT;
