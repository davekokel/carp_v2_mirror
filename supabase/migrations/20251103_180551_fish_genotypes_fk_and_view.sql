BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.transgenes'::regclass AND contype='p'
  ) THEN
    ALTER TABLE public.transgenes
      ADD CONSTRAINT pk_transgenes PRIMARY KEY (transgene_base_code);
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.transgene_alleles'::regclass AND contype='p'
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT pk_transgene_alleles PRIMARY KEY (transgene_base_code, allele_number);
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.transgene_alleles'::regclass
      AND conname='fk_ta_transgene_base'
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT fk_ta_transgene_base
      FOREIGN KEY (transgene_base_code)
      REFERENCES public.transgenes(transgene_base_code)
      ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
EXCEPTION WHEN duplicate_object THEN NULL;
END$$;

DO $$
DECLARE
  fish_col text;
BEGIN
  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_id') THEN 'fish_id'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_uuid') THEN 'fish_uuid'
           ELSE NULL
         END INTO fish_col;

  IF fish_col IS NOT NULL THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conrelid='public.join_fish_transgene_alleles'::regclass
        AND conname='fk_jfta_fish'
    ) THEN
      EXECUTE format($f$
        ALTER TABLE public.join_fish_transgene_alleles
        ADD CONSTRAINT fk_jfta_fish
        FOREIGN KEY (%I) REFERENCES public.fish(id)
        ON UPDATE CASCADE ON DELETE CASCADE NOT VALID
      $f$, fish_col);
    END IF;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_fish_transgene_alleles'::regclass
      AND conname='fk_jfta_allele'
  ) THEN
    ALTER TABLE public.join_fish_transgene_alleles
    ADD CONSTRAINT fk_jfta_allele
    FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
    ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
  END IF;
END$$;

CREATE OR REPLACE VIEW public.v_fish_genotypes_pretty AS
SELECT
  j.fish_id::text AS fish_id,
  string_agg(j.transgene_base_code||'['||j.allele_number::text||']', ', ' ORDER BY j.transgene_base_code, j.allele_number) AS genotype_pretty
FROM public.join_fish_transgene_alleles j
GROUP BY j.fish_id;

