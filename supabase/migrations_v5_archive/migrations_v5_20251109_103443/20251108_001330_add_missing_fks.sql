BEGIN;

-- Add composite FK from join_fish_transgene_alleles → transgene_alleles (if missing)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fk_jfta_ta'
      AND conrelid = 'public.join_fish_transgene_alleles'::regclass
  ) THEN
    ALTER TABLE public.join_fish_transgene_alleles
      ADD CONSTRAINT fk_jfta_ta
      FOREIGN KEY (transgene_base_code, allele_number)
      REFERENCES public.transgene_alleles (transgene_base_code, allele_number);
  END IF;
END $$;

COMMIT;
