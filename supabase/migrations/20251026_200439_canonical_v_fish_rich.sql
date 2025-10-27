DROP VIEW IF EXISTS public.v_fish_rich;

-- Canonical v_fish_rich with UUID and genotype_text for joins
CREATE VIEW public.v_fish_rich AS
SELECT
  f.fish_uuid::uuid AS fish_uuid,
  f.fish_code::text AS fish_code,
  COALESCE(g.genotype_text, NULL::text) AS genotype_text
FROM public.fish f
LEFT JOIN public.v_fish_genotypes g
  ON g.fish_code = f.fish_code;
