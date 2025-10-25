BEGIN;

-- Keep the unique guarantee on (fish_id, transgene_base_code); index is fine.
CREATE UNIQUE INDEX IF NOT EXISTS ux_fta_fish_base
  ON public.fish_transgene_alleles (fish_id, transgene_base_code);

-- Replace wrapper: rename OUT columns to avoid shadowing table cols
-- so ON CONFLICT (fish_id, transgene_base_code) parses unambiguously.
CREATE OR REPLACE FUNCTION public.upsert_fish_allele_from_csv(
  p_fish_id         uuid,
  p_base_code       text,
  p_allele_nickname text
)
RETURNS TABLE (ret_fish_id uuid, ret_transgene_base_code text, ret_allele_number int)
LANGUAGE plpgsql
AS $func$
DECLARE
  a_rec record;
BEGIN
  -- Get/reuse allele for (base_code, nickname). Nickname is treated as STRING.
  SELECT * INTO a_rec
  FROM public.ensure_allele_from_csv(p_base_code, p_allele_nickname);
  -- a_rec: (allele_number int, allele_name text, allele_nickname text)

  -- Link to fish; if row exists for (fish_id, base), update the allele number.
  RETURN QUERY
  INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
  VALUES (p_fish_id, p_base_code, a_rec.allele_number)
  ON CONFLICT (fish_id, transgene_base_code)
  DO UPDATE SET allele_number = EXCLUDED.allele_number
  RETURNING
    public.fish_transgene_alleles.fish_id,
    public.fish_transgene_alleles.transgene_base_code,
    public.fish_transgene_alleles.allele_number;
END
$func$;

COMMIT;
