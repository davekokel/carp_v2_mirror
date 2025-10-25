begin;

-- Drop prior versions so we can redefine signatures safely
drop function if exists public.gen_cross_genotype(text, text);
drop function if exists public.gen_fish_genotype(text);
drop function if exists public._allele_display(text, int, text);

-- Display rule for a single allele
create or replace function public._allele_display(p_base text, p_num int, p_nick text)
returns text
language sql
immutable
as $$
  SELECT COALESCE(NULLIF(p_nick, ''), 'Tg(' || p_base || ')' || p_num::text)
$$;

-- Build a fish genotype from (a) alias override, else (b) transgene alleles, else (c) fish_code
create or replace function public.gen_fish_genotype(p_fish_code text)
returns text
language sql
stable
as $$
  WITH alias AS (
    SELECT alias FROM public.cross_parent_aliases  WHERE parent_code = p_fish_code
  ),
  alleles AS (
    SELECT
      ta.transgene_base_code AS base,
      ta.allele_number       AS num,
      NULLIF(ta.allele_nickname, '') AS nick
    FROM public.fish AS f
    JOIN public.fish_transgene_alleles AS fta
      ON fta.fish_id = f.id
    JOIN public.transgene_alleles AS ta
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
create or replace function public.gen_cross_genotype(p_mom_code text, p_dad_code text)
returns text
language sql
stable
as $$
  SELECT public.gen_fish_genotype(p_mom_code) || ' × ' || public.gen_fish_genotype(p_dad_code)
$$;

-- Recompute all genotype names
update public.crosses
set cross_name_genotype = public.gen_cross_genotype(mother_code, father_code);

commit;
