BEGIN;

-- 1) transgene_alleles.transgene_base_code → transgenes.transgene_base_code
--    (declare the 1:n between the base table and its allele table)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_ta_transgene'
      AND conrelid='public.transgene_alleles'::regclass
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT fk_ta_transgene
      FOREIGN KEY (transgene_base_code)
      REFERENCES public.transgenes(transgene_base_code)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.transgene_alleles VALIDATE CONSTRAINT fk_ta_transgene;
  END IF;
END$$;

-- 2) join_fish_fluorescent_treatments.fish_code → fish.fish_code (TEXT→TEXT)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments'
      AND column_name='fish_code'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_jfft_fish_code'
        AND conrelid='public.join_fish_fluorescent_treatments'::regclass
    ) THEN
      ALTER TABLE public.join_fish_fluorescent_treatments
        ADD CONSTRAINT fk_jfft_fish_code
        FOREIGN KEY (fish_code)
        REFERENCES public.fish(fish_code)
        ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
      ALTER TABLE public.join_fish_fluorescent_treatments VALIDATE CONSTRAINT fk_jfft_fish_code;
    END IF;
  END IF;
END$$;

-- 3) join_fish_fluorescent_treatments.ft_code → fluorescent_treatments.ft_code (TEXT→TEXT)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments'
      AND column_name='ft_code'
  )
  AND EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fluorescent_treatments'
      AND column_name='ft_code'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint
      WHERE conname='fk_jfft_ft_code'
        AND conrelid='public.join_fish_fluorescent_treatments'::regclass
    ) THEN
      ALTER TABLE public.join_fish_fluorescent_treatments
        ADD CONSTRAINT fk_jfft_ft_code
        FOREIGN KEY (ft_code)
        REFERENCES public.fluorescent_treatments(ft_code)
        ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
      ALTER TABLE public.join_fish_fluorescent_treatments VALIDATE CONSTRAINT fk_jfft_ft_code;
    END IF;
  END IF;
END$$;

COMMIT;
