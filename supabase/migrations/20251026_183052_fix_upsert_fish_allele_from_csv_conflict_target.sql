-- Make sure the unique constraint/index exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_fta_fish_uuid_base'
  ) THEN
    CREATE UNIQUE INDEX uq_fta_fish_uuid_base
      ON public.fish_transgene_alleles(fish_uuid, transgene_base_code);
  END IF;
END $$;

DROP FUNCTION IF EXISTS public.upsert_fish_allele_from_csv(uuid, text, text);

CREATE FUNCTION public.upsert_fish_allele_from_csv(
  p_fish_uuid uuid,
  p_base_code text,
  p_allele_nickname text
)
RETURNS TABLE(fish_uuid uuid, transgene_base_code text, allele_number int)
LANGUAGE plpgsql
AS $$
DECLARE
  v_allele_number int;
  v_fu uuid;
  v_base text;
  v_anum int;
BEGIN
  -- Resolve an allele_number for (base_code, nickname); mint via helper if missing
  SELECT ta.allele_number
    INTO v_allele_number
  FROM public.transgene_alleles ta
  WHERE ta.transgene_base_code = p_base_code
    AND ta.allele_nickname = NULLIF(btrim(p_allele_nickname), '')
  LIMIT 1;

  IF v_allele_number IS NULL THEN
    SELECT u.allele_number
      INTO v_allele_number
    FROM public.upsert_transgene_allele(p_base_code, p_allele_nickname) AS u;
  END IF;

  -- Link or update per fish+base; avoid OUT-name clash by using the constraint name and qualifying RETURNING
  INSERT INTO public.fish_transgene_alleles (fish_uuid, transgene_base_code, allele_number)
  VALUES (p_fish_uuid, p_base_code, v_allele_number)
  ON CONFLICT ON CONSTRAINT uq_fta_fish_uuid_base
  DO UPDATE SET allele_number = EXCLUDED.allele_number
  RETURNING
    public.fish_transgene_alleles.fish_uuid,
    public.fish_transgene_alleles.transgene_base_code,
    public.fish_transgene_alleles.allele_number
  INTO v_fu, v_base, v_anum;

  fish_uuid := v_fu;
  transgene_base_code := v_base;
  allele_number := v_anum;
  RETURN NEXT;
END
$$;
