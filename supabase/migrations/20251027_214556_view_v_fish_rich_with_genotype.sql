DROP VIEW IF EXISTS public.v_fish_rich;

-- Minimal contract: ensure genotype_text exists (placeholder null for now)
CREATE VIEW public.v_fish_rich AS
SELECT
  f.fish_code::text AS fish_code,
  NULL::text        AS genotype_text
FROM public.fish f;
