BEGIN;

-- 1) Ensure the unique constraint on (fish_id, transgene_base_code)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE t.relname = 'fish_transgene_alleles'
      AND c.conname = 'uq_fta_fish_base'
  ) THEN
    ALTER TABLE public.fish_transgene_alleles
      ADD CONSTRAINT uq_fta_fish_base
      UNIQUE (fish_id, transgene_base_code);
  END IF;
END
$$;

-- 2) Recreate function to target the named constraint and qualify RETURNING
CREATE OR REPLACE FUNCTION public.upsert_fish_allele_from_csv(
  p_fish_id         uuid,
  p_base_code       text,
  p_allele_nickname text
)
RETURNS TABLE (fish_id uuid, transgene_base_code text, allele_number int)
LANGUAGE plpgsql
AS $func$
DECLARE
  a_rec record;
BEGIN
  -- Get or create the allele for (base_code, nickname). Nickname is treated as STRING.
  SELECT * INTO a_rec
  FROM public.ensure_allele_from_csv(p_base_code, p_allele_nickname);
  -- a_rec: (allele_number int, allele_name text, allele_nickname text)

  -- Link to fish; if row exists, update allele_number
  RETURN QUERY
  INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
  VALUES (p_fish_id, p_base_code, a_rec.allele_number)
  ON CONFLICT ON CONSTRAINT uq_fta_fish_base
  DO UPDATE SET allele_number = EXCLUDED.allele_number
  RETURNING
    public.fish_transgene_alleles.fish_id,
    public.fish_transgene_alleles.transgene_base_code,
    public.fish_transgene_alleles.allele_number;
END
$func$;

COMMIT;
