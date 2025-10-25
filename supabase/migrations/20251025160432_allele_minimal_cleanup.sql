BEGIN;

/* 1) Minimal unique guarantee (idempotent) */
CREATE UNIQUE INDEX IF NOT EXISTS ux_fta_fish_base
  ON public.fish_transgene_alleles (fish_id, transgene_base_code);

/* 2) Replace wrapper with non-colliding OUT names (drop first to allow signature change) */
DROP FUNCTION IF EXISTS public.upsert_fish_allele_from_csv(uuid, text, text);

CREATE FUNCTION public.upsert_fish_allele_from_csv(
  p_fish_id         uuid,
  p_base_code       text,
  p_allele_nickname text
)
RETURNS TABLE (
  ret_fish_id uuid,
  ret_transgene_base_code text,
  ret_allele_number int
)
LANGUAGE plpgsql
AS $func$
DECLARE
  a_rec record;  -- (allele_number int, allele_name text, allele_nickname text)
BEGIN
  -- Reuse-or-mint the allele for (base_code, nickname). Nickname is treated as STRING.
  SELECT * INTO a_rec
  FROM public.ensure_allele_from_csv(p_base_code, p_allele_nickname);

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
