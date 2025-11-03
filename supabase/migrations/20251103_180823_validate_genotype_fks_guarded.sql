BEGIN;

DO $$
DECLARE
  orphans_fish int := 0;
  orphans_alleles int := 0;
BEGIN
  SELECT count(*) INTO orphans_fish
  FROM public.join_fish_transgene_alleles j
  LEFT JOIN public.fish f ON f.id=j.fish_id
  WHERE f.id IS NULL;

  SELECT count(*) INTO orphans_alleles
  FROM public.join_fish_transgene_alleles j
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code=j.transgene_base_code
   AND ta.allele_number=j.allele_number
  WHERE ta.transgene_base_code IS NULL;

  IF orphans_fish=0 THEN
    BEGIN
      ALTER TABLE public.join_fish_transgene_alleles VALIDATE CONSTRAINT fk_jfta_fish;
    EXCEPTION WHEN undefined_object THEN
      NULL;
    END;
  ELSE
    RAISE NOTICE 'Skipped VALIDATE fk_jfta_fish (% orphan fish rows)', orphans_fish;
  END IF;

  IF orphans_alleles=0 THEN
    BEGIN
      ALTER TABLE public.join_fish_transgene_alleles VALIDATE CONSTRAINT fk_jfta_allele;
    EXCEPTION WHEN undefined_object THEN
      NULL;
    END;
  ELSE
    RAISE NOTICE 'Skipped VALIDATE fk_jfta_allele (% orphan allele rows)', orphans_alleles;
  END IF;
END$$;

COMMIT;
