BEGIN;

-- 1. genotypes: canonical genotype definitions
CREATE TABLE IF NOT EXISTS public.genotypes (
  genotype_code        text PRIMARY KEY,
  genotype_name        text,
  genotype_pretty      text,
  genetic_background   text,
  source_system        text,
  notes                text
);

-- 2. genotype_transgene_alleles: link genotypes to specific alleles
CREATE TABLE IF NOT EXISTS public.genotype_transgene_alleles (
  genotype_code        text NOT NULL,
  transgene_base_code  text NOT NULL,
  allele_number        integer NOT NULL,
  zygosity             text,
  PRIMARY KEY (genotype_code, transgene_base_code, allele_number),
  FOREIGN KEY (genotype_code)
    REFERENCES public.genotypes(genotype_code)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
    ON UPDATE CASCADE ON DELETE RESTRICT
);

-- 3. Hook fish_instance to genotypes
ALTER TABLE public.fish_instance
ADD COLUMN IF NOT EXISTS standard_genotype_code text
  REFERENCES public.genotypes(genotype_code)
  ON UPDATE CASCADE ON DELETE SET NULL;

-- 4. Hook crosses + clutches to genotypes (expected vs observed)
ALTER TABLE public.crosses
ADD COLUMN IF NOT EXISTS expected_genotype_code text
  REFERENCES public.genotypes(genotype_code)
  ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE public.clutches
ADD COLUMN IF NOT EXISTS observed_genotype_code text
  REFERENCES public.genotypes(genotype_code)
  ON UPDATE CASCADE ON DELETE SET NULL;

COMMIT;
