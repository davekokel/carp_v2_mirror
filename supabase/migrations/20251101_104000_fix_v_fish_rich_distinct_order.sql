BEGIN;
DROP VIEW IF EXISTS public.v_fish_rich;
CREATE VIEW public.v_fish_rich AS
SELECT
  f.*,
  COALESCE(v.genotype_pretty,'') AS genotype_text
FROM public.fish f
LEFT JOIN public.v_fish_genotypes_pretty v
  ON v.fish_id = f.id::text;
COMMIT;
