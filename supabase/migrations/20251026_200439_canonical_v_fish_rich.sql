DROP VIEW IF EXISTS public.v_fish_rich;

-- Canonical minimal contract (guarantees genotype_text exists for later joins)
CREATE VIEW public.v_fish_rich AS
SELECT
  f.fish_code::text AS fish_code,
  NULL::text        AS genotype_text
FROM public.fish f;
