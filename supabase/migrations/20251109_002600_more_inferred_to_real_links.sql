BEGIN;

CREATE INDEX IF NOT EXISTS idx_jfft_ft_code           ON public.join_fish_fluorescent_treatments(ft_code);
CREATE INDEX IF NOT EXISTS idx_ftdyes_ft_code         ON public.ft_dyes(ft_code);
CREATE INDEX IF NOT EXISTS idx_ftdyes_dye_code        ON public.ft_dyes(dye_code);
CREATE INDEX IF NOT EXISTS idx_ftproteins_ft_code     ON public.ft_proteins(ft_code);
CREATE INDEX IF NOT EXISTS idx_ftproteins_fluor_code  ON public.ft_proteins(fluor_code);
CREATE INDEX IF NOT EXISTS idx_ftproteins_tag_code    ON public.ft_proteins(tag_code);
CREATE INDEX IF NOT EXISTS idx_jftga_base_allele      ON public.join_fish_transgene_alleles(transgene_base_code, allele_number);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_jfft_ft_code__treatments_fluorescent'
      AND conrelid='public.join_fish_fluorescent_treatments'::regclass
  ) THEN
    ALTER TABLE public.join_fish_fluorescent_treatments
      ADD CONSTRAINT fk_jfft_ft_code__treatments_fluorescent
      FOREIGN KEY (ft_code) REFERENCES public.treatments_fluorescent(ft_code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_ft_dyes_ft_code__treatments_fluorescent'
      AND conrelid='public.ft_dyes'::regclass
  ) THEN
    ALTER TABLE public.ft_dyes
      ADD CONSTRAINT fk_ft_dyes_ft_code__treatments_fluorescent
      FOREIGN KEY (ft_code) REFERENCES public.treatments_fluorescent(ft_code)
      ON UPDATE RESTRICT ON DELETE CASCADE
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_ft_dyes_dye_code__dyes'
      AND conrelid='public.ft_dyes'::regclass
  ) THEN
    ALTER TABLE public.ft_dyes
      ADD CONSTRAINT fk_ft_dyes_dye_code__dyes
      FOREIGN KEY (dye_code) REFERENCES public.dyes(dye_code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_ft_proteins_ft_code__treatments_fluorescent'
      AND conrelid='public.ft_proteins'::regclass
  ) THEN
    ALTER TABLE public.ft_proteins
      ADD CONSTRAINT fk_ft_proteins_ft_code__treatments_fluorescent
      FOREIGN KEY (ft_code) REFERENCES public.treatments_fluorescent(ft_code)
      ON UPDATE RESTRICT ON DELETE CASCADE
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_ft_proteins_fluor_code__fluors'
      AND conrelid='public.ft_proteins'::regclass
  ) THEN
    ALTER TABLE public.ft_proteins
      ADD CONSTRAINT fk_ft_proteins_fluor_code__fluors
      FOREIGN KEY (fluor_code) REFERENCES public.fluors(fluor_code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_ft_proteins_tag_code__tags'
      AND conrelid='public.ft_proteins'::regclass
  ) THEN
    ALTER TABLE public.ft_proteins
      ADD CONSTRAINT fk_ft_proteins_tag_code__tags
      FOREIGN KEY (tag_code) REFERENCES public.tags(tag_code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_jftga_base_allele__transgene_alleles'
      AND conrelid='public.join_fish_transgene_alleles'::regclass
  ) THEN
    ALTER TABLE public.join_fish_transgene_alleles
      ADD CONSTRAINT fk_jftga_base_allele__transgene_alleles
      FOREIGN KEY (transgene_base_code, allele_number)
      REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

COMMIT;
