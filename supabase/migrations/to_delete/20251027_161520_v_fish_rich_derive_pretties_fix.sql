DROP VIEW IF EXISTS public.v_fish_rich_derive_pretties CASCADE;
CREATE VIEW public.v_fish_rich_derive_pretties AS
WITH base AS (
  SELECT
    f.fish_uuid,
    f.fish_code,
    f.genetic_background,
    f.line_building_stage
  FROM public.fish f
),
geno AS (
  SELECT
    fta.fish_uuid,
    string_agg(
      'Tg(' || fta.transgene_base_code || ')' || COALESCE(ta.allele_nickname,''),
      '; ' ORDER BY fta.transgene_base_code, fta.allele_number
    ) AS genotype_text
  FROM public.fish_transgene_alleles fta
  LEFT JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = fta.transgene_base_code
   AND ta.anchored = true
   AND ta.allele_number = fta.allele_number
  GROUP BY fta.fish_uuid
)
SELECT
  b.fish_uuid,
  b.fish_code,
  b.genetic_background,
  b.line_building_stage,
  COALESCE(geno.genotype_text,'') AS genotype_text
FROM base b
LEFT JOIN geno ON geno.fish_uuid = b.fish_uuid;
