-- Ensure ON CONFLICT target exists (noop if already present)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_fta_fish_uuid_base'
  ) THEN
    CREATE UNIQUE INDEX uq_fta_fish_uuid_base
      ON public.fish_transgene_alleles(fish_uuid, transgene_base_code);
  END IF;
END
$$;

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
BEGIN
  -- Try to find an existing allele number for (base_code, nickname)
  SELECT ta.allele_number
    INTO v_allele_number
  FROM public.transgene_alleles ta
  WHERE ta.transgene_base_code = p_base_code
    AND ta.allele_nickname = NULLIF(btrim(p_allele_nickname), '')
  LIMIT 1;

  -- Otherwise mint/reuse via helper; alias its output and read the column explicitly
  IF v_allele_number IS NULL THEN
    SELECT u.allele_number
      INTO v_allele_number
    FROM public.upsert_transgene_allele(p_base_code, p_allele_nickname) AS u;
  END IF;

  -- Link or update (per-base) for this fish
  RETURN QUERY
  INSERT INTO public.fish_transgene_alleles (fish_uuid, transgene_base_code, allele_number)
  VALUES (p_fish_uuid, p_base_code, v_allele_number)
  ON CONFLICT (fish_uuid, transgene_base_code)
  DO UPDATE SET allele_number = EXCLUDED.allele_number
  RETURNING fish_uuid, transgene_base_code, allele_number;
END
$$;
