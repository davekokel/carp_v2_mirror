-- Ensure the unique constraint exists for ON CONFLICT to work cleanly
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname='public'
      AND indexname = 'uq_fta_fish_uuid_base'
  ) THEN
    -- unique per fish per base code (allele_number can change via upsert)
    CREATE UNIQUE INDEX uq_fta_fish_uuid_base
      ON public.fish_transgene_alleles(fish_uuid, transgene_base_code);
  END IF;
END
$$;

-- Replace legacy function that referenced fish_id with a fish_uuid-safe version
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
  a_rec record;
BEGIN
  -- Resolve or mint the allele number for (base_code, nickname)
  SELECT ta.allele_number
  INTO a_rec
  FROM public.transgene_alleles ta
  WHERE ta.transgene_base_code = p_base_code
    AND ta.allele_nickname = NULLIF(btrim(p_allele_nickname), '')
  LIMIT 1;

  IF a_rec IS NULL THEN
    -- Reuse your canonical helper to create/find the allele
    SELECT allele_number
    INTO a_rec
    FROM public.upsert_transgene_allele(p_base_code, p_allele_nickname);
  END IF;

  -- Link fish ↔ base using the resolved allele_number.
  -- If a row already exists for (fish_uuid, base_code), update its allele_number.
  RETURN QUERY
  INSERT INTO public.fish_transgene_alleles (fish_uuid, transgene_base_code, allele_number)
  VALUES (p_fish_uuid, p_base_code, a_rec.allele_number)
  ON CONFLICT (fish_uuid, transgene_base_code)
  DO UPDATE SET allele_number = EXCLUDED.allele_number
  RETURNING
    public.fish_transgene_alleles.fish_uuid,
    public.fish_transgene_alleles.transgene_base_code,
    public.fish_transgene_alleles.allele_number;
END
$$;
