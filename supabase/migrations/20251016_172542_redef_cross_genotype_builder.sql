BEGIN;

-- Drop prior versions so we can redefine signatures safely
DROP FUNCTION IF EXISTS public.gen_cross_genotype(text,text);
DROP FUNCTION IF EXISTS public.gen_fish_genotype(text);
DROP FUNCTION IF EXISTS public._allele_display(text,int,text);

-- Display rule for a single allele
CREATE OR REPLACE FUNCTION public._allele_display(p_base text, p_num int, p_nick text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT COALESCE(NULLIF(p_nick,''), 'Tg(' || p_base || ')' || p_num::text)
$$;

-- Build a fish genotype from (a) alias override, else (b) transgene alleles, else (c) fish_code
CREATE OR REPLACE FUNCTION public.gen_fish_genotype(p_fish_code text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
  WITH alias AS (
    SELECT alias FROM public.cross_parent_aliases WHERE parent_code = p_fish_code
  ),
  alleles AS (
    SELECT
      ta.transgene_base_code AS base,
      ta.allele_number       AS num,
      NULLIF(ta.allele_nickname,'') AS nick
    FROM public.fish f
    JOIN public.fish_transgene_alleles fta
      ON fta.fish_id = f.id
    JOIN public.transgene_alleles ta
      ON ta.transgene_base_code = fta.transgene_base_code
     AND ta.allele_number       = fta.allele_number
    WHERE f.fish_code = p_fish_code
  ),
  built AS (
    SELECT STRING_AGG(public._allele_display(base,num,nick), ' + ' ORDER BY base, num) AS g
    FROM alleles
  )
  SELECT
    COALESCE( (SELECT alias FROM alias),
              NULLIF((SELECT g FROM built), ''),
              p_fish_code )
$$;

-- Cross genotype = mom_genotype × dad_genotype
CREATE OR REPLACE FUNCTION public.gen_cross_genotype(p_mom_code text, p_dad_code text)
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT public.gen_fish_genotype(p_mom_code) || ' × ' || public.gen_fish_genotype(p_dad_code)
$$;

-- Recompute all genotype names
UPDATE public.crosses
SET cross_name_genotype = public.gen_cross_genotype(mother_code, father_code);

COMMIT;
