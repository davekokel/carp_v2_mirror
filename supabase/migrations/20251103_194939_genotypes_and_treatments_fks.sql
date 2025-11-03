BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.transgene_alleles'::regclass AND contype='p') THEN
    ALTER TABLE public.transgene_alleles ADD CONSTRAINT pk_transgene_alleles PRIMARY KEY (transgene_base_code, allele_number);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.transgene_alleles'::regclass AND conname='fk_ta_transgene_base') THEN
    ALTER TABLE public.transgene_alleles ADD CONSTRAINT fk_ta_transgene_base
      FOREIGN KEY (transgene_base_code) REFERENCES public.transgenes(transgene_base_code)
      ON UPDATE CASCADE ON DELETE RESTRICT;
  END IF;
END$$;

DO $$
DECLARE fish_col text;
BEGIN
  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_id') THEN 'fish_id'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_uuid') THEN 'fish_uuid'
           ELSE NULL
         END INTO fish_col;
  IF fish_col IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid='public.join_fish_transgene_alleles'::regclass AND conname='fk_jfta_fish'
  ) THEN
    EXECUTE format($f$
      ALTER TABLE public.join_fish_transgene_alleles
      ADD CONSTRAINT fk_jfta_fish
      FOREIGN KEY (%I) REFERENCES public.fish(id)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID
    $f$, fish_col);
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conrelid='public.join_fish_transgene_alleles'::regclass AND conname='fk_jfta_allele'
  ) THEN
    ALTER TABLE public.join_fish_transgene_alleles
    ADD CONSTRAINT fk_jfta_allele
    FOREIGN KEY (transgene_base_code, allele_number)
    REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
    ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
  END IF;
END$$;

DO $$
DECLARE nf int := 0; na int := 0;
BEGIN
  SELECT count(*) INTO nf
  FROM public.join_fish_transgene_alleles j
  LEFT JOIN public.fish f ON f.id=j.fish_id
  WHERE f.id IS NULL;
  IF nf=0 THEN
    BEGIN ALTER TABLE public.join_fish_transgene_alleles VALIDATE CONSTRAINT fk_jfta_fish; EXCEPTION WHEN undefined_object THEN NULL; END;
  END IF;

  SELECT count(*) INTO na
  FROM public.join_fish_transgene_alleles j
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code=j.transgene_base_code AND ta.allele_number=j.allele_number
  WHERE ta.transgene_base_code IS NULL;
  IF na=0 THEN
    BEGIN ALTER TABLE public.join_fish_transgene_alleles VALIDATE CONSTRAINT fk_jfta_allele; EXCEPTION WHEN undefined_object THEN NULL; END;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.treatments'::regclass AND conname='fk_treatments_plasmid_code'
  ) THEN
    ALTER TABLE public.treatments
    ADD CONSTRAINT fk_treatments_plasmid_code
    FOREIGN KEY (plasmid_code) REFERENCES public.plasmids(code)
    ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;
  END IF;
END$$;

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
  FROM public.treatments t
  LEFT JOIN public.plasmids p ON p.code=t.plasmid_code
  WHERE t.plasmid_code IS NOT NULL AND p.code IS NULL;
  IF n=0 THEN
    BEGIN ALTER TABLE public.treatments VALIDATE CONSTRAINT fk_treatments_plasmid_code; EXCEPTION WHEN undefined_object THEN NULL; END;
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_jfta_fish ON public.join_fish_transgene_alleles(fish_id);
CREATE INDEX IF NOT EXISTS idx_jfta_allele ON public.join_fish_transgene_alleles(transgene_base_code, allele_number);
CREATE INDEX IF NOT EXISTS idx_treatments_plasmid_code ON public.treatments(plasmid_code);

COMMIT;
