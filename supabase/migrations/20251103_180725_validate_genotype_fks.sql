BEGIN;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_fish_transgene_alleles'::regclass
      AND conname='fk_jfta_fish'
  ) THEN
    BEGIN
      ALTER TABLE public.join_fish_transgene_alleles VALIDATE CONSTRAINT fk_jfta_fish;
    EXCEPTION WHEN undefined_object THEN
      NULL;
    END;
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.join_fish_transgene_alleles'::regclass
      AND conname='fk_jfta_allele'
  ) THEN
    BEGIN
      ALTER TABLE public.join_fish_transgene_alleles VALIDATE CONSTRAINT fk_jfta_allele;
    EXCEPTION WHEN undefined_object THEN
      NULL;
    END;
  END IF;
END$$;
COMMIT;
